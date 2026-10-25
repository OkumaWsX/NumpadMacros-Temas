# Temas de Numpad Macros

Catálogo de temas que Numpad Macros muestra en su pestaña **Temas**, para descargar con un clic.
Los temas viven aquí y no en el repositorio de la app: publicar o actualizar un tema **no requiere
sacar una versión nueva de Numpad Macros**.

## Estructura

```
oficiales/<id>/
    ficha.json              descripción y etiquetas (opcional)
    <versión>/tema.npt      el tema firmado con la clave oficial
creadores/<creador>/
    creador.json            nombre, bio y redes sociales del creador (una vez, para todos sus temas)
creadores/<creador>/<id>/
    ficha.json              descripción, etiquetas y «creador» (nombre visible)
    <versión>/tema.npt      firmado con la clave oficial, tras revisarlo OkumaWsX
comunidad/<autor>/<id>/
    ficha.json
    <versión>/tema.npt      firmado con la firma de autor (Estudio de Temas)
catalogo.json               lo arma GitHub solo: no se edita a mano
tools/armar_catalogo.py     revisa los temas y arma el catálogo
```

- `<id>`, `<creador>` y `<autor>`: minúsculas, números y guiones (por ejemplo `dos-mares`).
- `<versión>`: la misma que tiene el tema por dentro (`1.0`, `1.2`…). Cada versión va en su propia
  carpeta y nunca se reemplaza: así la app no mezcla archivos viejos y nuevos.

## Publicar o actualizar un tema oficial

1. Exporta el tema desde el Estudio de Temas (con la clave oficial).
2. Cópialo como `oficiales/<id>/<versión>/tema.npt` (y, si quieres, crea o edita `ficha.json`).
3. Súbelo a `main`. GitHub revisa el tema y actualiza `catalogo.json` solo.

Si algo está mal (firma, versión, tamaño, nombre repetido), la revisión falla y dice qué corregir.

## Temas de creadores digitales

Temas hechos por streamers, artistas y otros creadores. Los revisa y **firma OkumaWsX con la clave
oficial** (la misma de los temas oficiales); en la app llevan el sello **★ CREADOR** y el nombre del creador.

1. Revisa el tema y expórtalo con la clave oficial desde el Estudio de Temas.
2. Cópialo como `creadores/<creador>/<id>/<versión>/tema.npt`. `<creador>` es el nombre de la carpeta
   del creador (minúsculas, números y guiones; por ejemplo `aquamanchileno`).
3. Crea `creadores/<creador>/<id>/ficha.json` con `"creador": "NombreVisible"` (si falta, se usa el
   nombre de la carpeta) y, si quieres, `descripcion` y `etiquetas`.
4. Crea (una sola vez) `creadores/<creador>/creador.json` con sus datos; vale para todos sus temas (ver
   «`creador.json`» más abajo).
5. Súbelo a `main`; GitHub lo revisa y actualiza `catalogo.json`.

Un archivo en `creadores/` sin la firma oficial se rechaza, igual que uno de `oficiales/` mal firmado:
la carpeta no basta para hacerse pasar por creador.

## Temas de la comunidad

Pasan por la aprobación de OkumaWsX antes de publicarse. La forma de enviarlos (canal de Discord y
normas) se definirá más adelante.

## Seguridad

- El sello **Oficial**, **Creador** o **Comunidad** y el **autor** salen de la **firma** del archivo, nunca de la
  carpeta ni de la ficha: nadie puede hacer pasar un tema por oficial o de creador ni usar el nombre de otra persona.
- `catalogo.json` incluye la huella **SHA256** de cada archivo; la app la comprueba antes de instalar.

## `ficha.json`

```json
{
 "descripcion": "Texto corto (hasta 200 letras).",
 "etiquetas": ["oscuro", "imágenes"],
 "requiere_app": "3.5.0"
}
```

`requiere_app` (opcional): versión mínima de Numpad Macros que puede usar el tema. Las versiones
más antiguas no lo muestran, en vez de fallar.

## `creador.json`

La ficha del creador que la app muestra en el detalle de sus temas («★ CREADOR DIGITAL»): nombre, una
bio corta y sus redes sociales.

```json
{
 "nombre": "AquamanChileno",
 "bio": "Creador chileno de terror y terror psicológico.",
 "redes": [
  {"red": "twitch", "url": "https://www.twitch.tv/aquamanchileno"},
  {"red": "youtube", "url": "https://www.youtube.com/@AquamanChileno"}
 ],
 "avatar": "avatar.png"
}
```

Se revisa de forma estricta y, si algo no cumple, la revisión falla diciendo qué corregir:

- `nombre`: obligatorio, hasta 40 letras. `bio`: hasta 300 caracteres (opcional).
- `red`: una de `twitch`, `youtube`, `tiktok`, `kick`, `instagram`, `x`, `facebook`, `discord`; sin repetir.
- `url`: empieza con `https://`, sin usuario, contraseña ni puerto, y su sitio es el oficial de esa red
  (o un subdominio suyo): `twitch.tv`; `youtube.com` o `youtu.be`; `tiktok.com`; `kick.com`;
  `instagram.com`; `x.com` o `twitter.com`; `facebook.com`; `discord.gg` o `discord.com`.
  Por ejemplo `https://twitch.tv.evil.com/…` se rechaza.
- Las redes que el creador no tiene, simplemente no se ponen.
- `avatar` (opcional): su foto de perfil, un archivo de la misma carpeta (`creadores/<creador>/avatar.png`).
  Debe ser un **PNG o JPEG de verdad** (se mira el contenido, no solo la extensión), pesar **hasta 200 KB**,
  ser **cuadrada o casi** y medir **entre 64 y 512 px** por lado (recomendado: 256×256). Solo se publica con
  autorización del creador. Si no cumple, la revisión falla diciendo qué corregir. El armador calcula su huella
  SHA256 y publica `creador_info.avatar = {"archivo", "sha256", "tamano"}`.

La app vuelve a comprobar cada enlace con las mismas reglas antes de mostrarlo (el catálogo no está
firmado) y nunca abre uno que no las cumpla. La foto la baja en segundo plano, comprueba su huella SHA256,
su tamaño y que sea una imagen cuadrada de 64 a 512 px antes de usarla, y la guarda en su caché; mientras
tanto (o si algo falla) se ve la inicial del creador.

## `catalogo.json` (formato 1)

Cada tema trae: `id`, `origen` (`oficial`/`creador`/`comunidad`), `nombre`, `autor`, `creador` (solo en temas de creadores), `huella_autor`, `version`,
`fecha`, `descripcion`, `etiquetas`, `requiere_app`, `archivo`, `sha256`, `tamano`, `estilo`
(`oscuro`/`claro`), `color` (del acento), `colores` (para la miniatura) y `extras`
(`imagenes`, `animado`, `transparencia`, `degradado`). Los temas de creadores traen además `creador_info`
(`nombre`, `bio`, `redes` y, si tiene foto, `avatar`: lo que dice su `creador.json`). La app ignora los campos que no conoce.
