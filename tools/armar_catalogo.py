# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (C) 2026 OkumaWsX
"""Revisa los temas del repositorio y arma catalogo.json (lo que lee Numpad Macros).

Estructura:
    oficiales/<id>/<versión>/tema.npt                firmado con la clave oficial
    comunidad/<autor>/<id>/<versión>/tema.npt         firmado con la firma de autor
    .../<id>/ficha.json                               opcional: descripción, etiquetas, requiere_app

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
from datetime import datetime, timezone

FORMATO = 1                       # versión del formato del catálogo (la app ignora lo que no conoce)
REQUIERE_APP = "3.5.0"            # versión mínima de Numpad Macros si la ficha no dice otra
ID_OK = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
VER_OK = re.compile(r"^\d+(\.\d+){0,2}$")
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


def revisar_tema(npt, raiz, origen, autor_dir, tid, carpeta, errores):
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
        acc = t.colors.get("acc", "#888888")
        entrada = {
            "id": f"{origen}/{autor_dir + '/' if autor_dir else ''}{tid}",
            "origen": origen,
            "nombre": t.name,
            "autor": npt.OFFICIAL_NAME if r.official else (t.author or "Anónimo"),
            "huella_autor": npt.fingerprint(r.author_key) if r.author_key else "",
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
    base = os.path.join(raiz, "comunidad")
    for autor in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        adir = os.path.join(base, autor)
        if not os.path.isdir(adir):
            continue
        if not ID_OK.match(autor):
            errores.append(f"comunidad/{autor}: el nombre de la carpeta debe ir en minúsculas, números y guiones")
            continue
        for tid in sorted(os.listdir(adir)):
            if os.path.isdir(os.path.join(adir, tid)):
                e = revisar_tema(npt, raiz, "comunidad", autor, tid, os.path.join(adir, tid), errores)
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
    args = ap.parse_args()
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
