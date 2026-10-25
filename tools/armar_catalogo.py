# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Revisa los temas del repositorio y arma catalogo.json (lo que lee Numpad Macros).

Estructura:
    oficiales/<id>/<versión>/tema.npt                firmado con la clave oficial
    creadores/<creador>/<id>/<versión>/tema.npt       firmado con la clave oficial (lo revisa y firma OkumaWsX)
    comunidad/<autor>/<id>/<versión>/tema.npt         firmado con la firma de autor
    .../<id>/ficha.json                               opcional: descripción, etiquetas, requiere_app
                                                      (creadores: también «creador», el nombre visible)
    creadores/<creador>/creador.json                  opcional: nombre, bio, redes sociales y foto («avatar») del creador
                                                      (se escribe una vez aunque tenga varios temas)

Todo lo que se muestra (nombre, autor, versión, oficial o comunidad) sale del propio .npt y de su
firma, nunca de lo que diga una carpeta o una ficha: así nadie puede hacer pasar un tema por oficial.

    python tools/armar_catalogo.py --app ../NumpadMacros            # revisa y escribe catalogo.json
    python tools/armar_catalogo.py --app ../NumpadMacros --revisar  # solo revisa (para Pull Requests)
"""
import argparse
import colorsys
import hashlib
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone

FORMATO = 1                       # versión del formato del catálogo (la app ignora lo que no conoce)
REQUIERE_APP = "3.5.0"            # versión mínima de Numpad Macros si la ficha no dice otra
ID_OK = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
VER_OK = re.compile(r"^\d+(\.\d+){0,2}$")
# redes sociales de un creador: dominios oficiales (la app comprueba lo mismo, en red_url_valida de npm/catalogo.py)
REDES = {"twitch": ("twitch.tv",), "youtube": ("youtube.com", "youtu.be"), "tiktok": ("tiktok.com",),
         "kick": ("kick.com",), "instagram": ("instagram.com",), "x": ("x.com", "twitter.com"),
         "facebook": ("facebook.com",), "discord": ("discord.gg", "discord.com")}
BIO_MAX = 300
# foto de perfil del creador (la app comprueba lo mismo, en avatar_valido de npm/catalogo.py)
AVATAR_MAX = 200 * 1024           # bytes
AVATAR_PX = (64, 512)             # lado mínimo y máximo, en píxeles
AVATAR_ASPECTO = 1.1              # cuánto puede alejarse de un cuadrado (lado mayor / lado menor)
COLORES = (("rojo", 0), ("naranja", 25), ("amarillo", 50), ("verde", 120), ("celeste", 185),
           ("azul", 225), ("morado", 270), ("rosa", 320), ("rojo", 360))


def parse_version(v):
    return tuple(int(n) for n in v.split(".")) + (0,) * (3 - len(v.split(".")))


def color_principal(hexcol):
    """El color de acento como nombre simple (para el filtro «Color»)."""
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < .18 or l < .08 or l > .95:
        return "gris"
    deg = h * 360
    return min(COLORES, key=lambda c: abs(c[1] - deg))[0]


def leer_ficha(carpeta, errores):
    path = os.path.join(carpeta, "ficha.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            ficha = json.load(f)
    except (OSError, ValueError) as e:
        errores.append(f"{path}: no se puede leer ({e})")
        return {}
    if not isinstance(ficha, dict):
        errores.append(f"{path}: debe ser un objeto JSON")
        return {}
    return ficha


def url_red_error(red, url):
    """Por qué ``url`` no vale para la red ``red`` (None si vale): https, sin usuario ni puerto, y un host
    que sea el dominio oficial de la red o un subdominio suyo (twitch.tv.evil.com no lo es)."""
    if not isinstance(url, str) or not url:
        return "falta la URL"
    if not url.isascii() or len(url) > 300 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 or c in "\\<>\"'`" for c in url):
        return "la URL tiene caracteres no permitidos o es demasiado larga"
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except ValueError:
        return "la URL no es válida"
    host = (p.hostname or "").lower()
    if p.scheme != "https":
        return "la URL debe empezar con https://"
    if "@" in p.netloc or p.username or p.password:
        return "la URL no puede llevar usuario ni contraseña"
    if port is not None:
        return "la URL no puede llevar puerto"
    if p.netloc.lower() != host or not host:
        return "la URL no es válida"
    if not any(host == d or host.endswith("." + d) for d in REDES[red]):
        return f"«{host}» no es un dominio oficial de {red} ({', '.join(REDES[red])})"
    return None


def medir_imagen(datos):
    """(formato, ancho, alto) de un PNG o JPEG leyendo su cabecera (bytes mágicos), o None si no lo es.
    No depende de Pillow: solo mira la cabecera, sin decodificar la imagen."""
    if datos[:8] == b"\x89PNG\r\n\x1a\n" and datos[12:16] == b"IHDR" and len(datos) >= 24:
        return "png", int.from_bytes(datos[16:20], "big"), int.from_bytes(datos[20:24], "big")
    if datos[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 < len(datos):
            if datos[i] != 0xFF:
                return None
            m = datos[i + 1]
            if m == 0xFF:                       # relleno entre marcadores
                i += 1
                continue
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            largo = int.from_bytes(datos[i + 2:i + 4], "big")
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):       # SOFn: trae el tamaño
                return "jpeg", int.from_bytes(datos[i + 7:i + 9], "big"), int.from_bytes(datos[i + 5:i + 7], "big")
            if m == 0xDA or largo < 2:          # empieza la imagen sin haber visto el tamaño
                return None
            i += 2 + largo
    return None


def leer_avatar(carpeta, rel, nombre, errores):
    """Valida la foto de perfil ``nombre`` (archivo en la carpeta del creador). Devuelve
    {"archivo", "sha256", "tamano"} o None (los motivos se suman a ``errores``)."""
    rp = f"{rel}/creador.json"
    if (not isinstance(nombre, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,60}\.(png|jpe?g)$", nombre, re.I)
            or ".." in nombre):
        errores.append(f"{rp}: «avatar» debe ser el nombre de un archivo .png o .jpg de esta misma carpeta "
                       "(por ejemplo \"avatar.png\")")
        return None
    path = os.path.join(carpeta, nombre)
    if os.path.islink(path) or not os.path.isfile(path):
        errores.append(f"{rel}/{nombre}: no existe (el «avatar» de creador.json debe estar en la carpeta del creador)")
        return None
    tam = os.path.getsize(path)
    if tam > AVATAR_MAX:
        errores.append(f"{rel}/{nombre}: pesa {tam // 1024} KB y el máximo es {AVATAR_MAX // 1024} KB; "
                       "reduce su tamaño o expórtalo con menos calidad")
        return None
    with open(path, "rb") as f:
        datos = f.read()
    med = medir_imagen(datos)
    if med is None:
        errores.append(f"{rel}/{nombre}: no es una imagen PNG o JPEG válida (se mira el contenido, no la extensión)")
        return None
    formato, ancho, alto = med
    mal = False
    if not nombre.lower().endswith((".png",) if formato == "png" else (".jpg", ".jpeg")):
        errores.append(f"{rel}/{nombre}: es una imagen {formato.upper()} pero la extensión no coincide")
        mal = True
    lo, hi = AVATAR_PX
    if min(ancho, alto) < lo or max(ancho, alto) > hi:
        errores.append(f"{rel}/{nombre}: mide {ancho}×{alto} px; debe medir entre {lo} y {hi} px por lado")
        mal = True
    elif max(ancho, alto) > min(ancho, alto) * AVATAR_ASPECTO:
        errores.append(f"{rel}/{nombre}: mide {ancho}×{alto} px; debe ser cuadrada (o casi)")
        mal = True
    if mal:
        return None
    try:                                        # si hay Pillow, que de verdad se pueda abrir completa
        from PIL import Image
        import io
        with Image.open(io.BytesIO(datos)) as im:
            im.load()
    except ImportError:
        pass
    except Exception as e:
        errores.append(f"{rel}/{nombre}: la imagen está dañada ({e})")
        return None
    return {"archivo": f"{rel}/{nombre}", "sha256": hashlib.sha256(datos).hexdigest(), "tamano": len(datos)}


def leer_creador(carpeta, rel, errores):
    """Lee y valida creadores/<creador>/creador.json. Devuelve {"nombre", "bio", "redes"[, "avatar"]} o None
    (sin archivo o con errores: estos se suman a ``errores`` y el catálogo no se escribe)."""
    path = os.path.join(carpeta, "creador.json")
    if not os.path.isfile(path):
        return None
    rp = f"{rel}/creador.json"
    try:
        with open(path, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError) as e:
        errores.append(f"{rp}: no se puede leer ({e})")
        return None
    if not isinstance(datos, dict):
        errores.append(f"{rp}: debe ser un objeto JSON")
        return None
    n0 = len(errores)
    nombre, bio, redes = datos.get("nombre"), datos.get("bio", ""), datos.get("redes", [])
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 40:
        errores.append(f"{rp}: «nombre» es obligatorio (texto de hasta 40 letras)")
    if not isinstance(bio, str) or len(bio) > BIO_MAX:
        errores.append(f"{rp}: «bio» debe ser texto de hasta {BIO_MAX} caracteres"
                       + (f" (tiene {len(bio)})" if isinstance(bio, str) else ""))
    if not isinstance(redes, list):
        errores.append(f"{rp}: «redes» debe ser una lista de {{\"red\": …, \"url\": …}}")
        redes = []
    limpias, vistas = [], set()
    for i, r in enumerate(redes, 1):
        if not isinstance(r, dict):
            errores.append(f"{rp}: la red {i} debe ser {{\"red\": …, \"url\": …}}")
            continue
        red = r.get("red")
        if not isinstance(red, str) or red not in REDES:
            errores.append(f"{rp}: la red {i} es «{red}»; las válidas son {', '.join(REDES)}")
            continue
        if red in vistas:
            errores.append(f"{rp}: la red «{red}» está repetida")
            continue
        vistas.add(red)
        motivo = url_red_error(red, r.get("url"))
        if motivo:
            errores.append(f"{rp}: {red}: {motivo}")
            continue
        limpias.append({"red": red, "url": r["url"]})
    avatar = leer_avatar(carpeta, rel, datos["avatar"], errores) if datos.get("avatar") is not None else None
    if len(errores) > n0:
        return None
    info = {"nombre": nombre.strip(), "bio": " ".join(bio.split()), "redes": limpias}
    if avatar:
        info["avatar"] = avatar
    return info


def revisar_tema(npt, raiz, origen, autor_dir, tid, carpeta, errores, creador=None):
    """Lee todas las versiones de un tema y devuelve la entrada del catálogo (la versión más nueva)."""
    rel = os.path.relpath(carpeta, raiz)
    if not ID_OK.match(tid):
        errores.append(f"{rel}: el nombre de la carpeta debe ir en minúsculas, números y guiones")
        return None
    ficha = leer_ficha(carpeta, errores)
    versiones = sorted((v for v in os.listdir(carpeta) if os.path.isdir(os.path.join(carpeta, v))),
                       key=lambda v: parse_version(v) if VER_OK.match(v) else (0,))
    if not versiones:
        errores.append(f"{rel}: no tiene ninguna versión (carpeta <versión>/tema.npt)")
        return None
    entrada = None
    for ver in versiones:
        vrel = f"{rel}/{ver}/tema.npt"
        path = os.path.join(carpeta, ver, "tema.npt")
        if not VER_OK.match(ver):
            errores.append(f"{rel}/{ver}: la carpeta debe ser un número de versión (1.0, 1.2…)")
            continue
        if not os.path.isfile(path):
            errores.append(f"{vrel}: falta el archivo")
            continue
        with open(path, "rb") as f:
            data = f.read()
        if len(data) > npt.MAX_SIZE:
            errores.append(f"{vrel}: pesa {len(data) // 1024} KB (máximo {npt.MAX_SIZE // 1024} KB)")
            continue
        try:
            r = npt.read(data)
        except npt.NptError as e:
            errores.append(f"{vrel}: no es un tema válido ({e})")
            continue
        t = r.theme
        if t.version != ver:
            errores.append(f"{vrel}: el tema dice versión {t.version}, pero está en la carpeta {ver}")
            continue
        if origen == "oficial" and not r.official:
            errores.append(f"{vrel}: está en «oficiales» pero no tiene la firma oficial")
            continue
        if origen == "creador" and not r.official:
            errores.append(f"{vrel}: está en «creadores» pero no tiene la firma oficial")
            continue
        if origen == "comunidad":
            if r.official:
                errores.append(f"{vrel}: tiene la firma oficial; va en «oficiales»")
                continue
            if r.format < 2 or not r.author_key:
                errores.append(f"{vrel}: los temas de la comunidad deben venir firmados por su autor (Estudio de Temas)")
                continue
            if r.reserved_name:
                errores.append(f"{vrel}: usa el nombre del creador oficial sin serlo")
                continue
        extra = {}
        if origen == "creador":                 # nombre visible: la ficha manda; si falta, la carpeta
            extra["creador"] = str(ficha.get("creador") or (creador or {}).get("nombre") or autor_dir).strip()[:40]
            if creador:                         # las apps viejas ignoran este campo
                extra["creador_info"] = creador
        acc = t.colors.get("acc", "#888888")
        entrada = {
            "id": f"{origen}/{autor_dir + '/' if autor_dir else ''}{tid}",
            "origen": origen,
            "nombre": t.name,
            "autor": npt.OFFICIAL_NAME if r.official else (t.author or "Anónimo"),
            "huella_autor": npt.fingerprint(r.author_key) if r.author_key else "",
            **extra,
            "version": t.version,
            "fecha": t.created,
            "descripcion": str(ficha.get("descripcion") or t.description or "")[:200],
            "etiquetas": [str(x)[:20] for x in (ficha.get("etiquetas") or [])][:8],
            "requiere_app": str(ficha.get("requiere_app") or REQUIERE_APP),
            "archivo": vrel.replace(os.sep, "/"),
            "sha256": hashlib.sha256(data).hexdigest(),
            "tamano": len(data),
            "estilo": t.kind,
            "color": color_principal(acc),
            "colores": dict(t.colors),
            "extras": {"imagenes": len(t.images), "animado": bool(t.animated),
                       "transparencia": bool(t.transparency), "degradado": bool(t.gradient)},
        }
    return entrada


def armar(app, raiz):
    sys.path.insert(0, os.path.abspath(app))
    from npm import npt                         # el mismo lector que usa la app
    errores, temas = [], []
    base = os.path.join(raiz, "oficiales")
    for tid in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if os.path.isdir(os.path.join(base, tid)):
            e = revisar_tema(npt, raiz, "oficial", "", tid, os.path.join(base, tid), errores)
            if e:
                temas.append(e)
    for origen, carpeta in (("creador", "creadores"), ("comunidad", "comunidad")):
        base = os.path.join(raiz, carpeta)
        for autor in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            adir = os.path.join(base, autor)
            if not os.path.isdir(adir):
                continue
            if not ID_OK.match(autor):
                errores.append(f"{carpeta}/{autor}: el nombre de la carpeta debe ir en minúsculas, números y guiones")
                continue
            creador = leer_creador(adir, f"{carpeta}/{autor}", errores) if origen == "creador" else None
            for tid in sorted(os.listdir(adir)):
                if os.path.isdir(os.path.join(adir, tid)):
                    e = revisar_tema(npt, raiz, origen, autor, tid, os.path.join(adir, tid), errores, creador)
                    if e:
                        temas.append(e)
    nombres = {}
    for t in temas:                             # dos temas con el mismo nombre confunden a la gente
        clave = (t["nombre"].casefold(), t["origen"])
        if clave in nombres:
            errores.append(f"«{t['nombre']}» está repetido ({nombres[clave]} y {t['id']})")
        nombres[clave] = t["id"]
    temas.sort(key=lambda t: (t["fecha"], t["nombre"].casefold()), reverse=True)
    return temas, errores


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--app", required=True, help="carpeta del código de Numpad Macros (para leer los .npt)")
    ap.add_argument("--revisar", action="store_true", help="solo revisar, sin escribir catalogo.json")
    ap.add_argument("--raiz", help="carpeta con oficiales/, creadores/ y comunidad/ (por defecto, este repositorio)")
    args = ap.parse_args()
    raiz = os.path.abspath(args.raiz) if args.raiz else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temas, errores = armar(args.app, raiz)
    for e in errores:
        print(f"::error::{e}" if os.environ.get("GITHUB_ACTIONS") else f"✘ {e}")
    print(f"{len(temas)} tema(s) válidos: "
          + ", ".join(f"{t['nombre']} {t['version']} ({t['origen']})" for t in temas))
    if errores:
        sys.exit(1)
    if args.revisar:
        return
    path = os.path.join(raiz, "catalogo.json")
    try:
        with open(path, encoding="utf-8") as f:
            antes = json.load(f)
    except (OSError, ValueError):
        antes = {}
    if antes.get("formato") == FORMATO and antes.get("temas") == temas:
        print("catalogo.json ya estaba al día")
        return
    cat = {"formato": FORMATO, "generado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "temas": temas}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("catalogo.json actualizado")


if __name__ == "__main__":
    main()
