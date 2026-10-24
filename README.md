# Temas de Numpad Macros

Catálogo de temas que Numpad Macros muestra en su pestaña **Temas**, para descargar con un clic.
Los temas viven aquí y no en el repositorio de la app: publicar o actualizar un tema **no requiere
sacar una versión nueva de Numpad Macros**.

## Estructura

```
oficiales/<id>/
    ficha.json              descripción y etiquetas (opcional)
    <versión>/tema.npt      el tema firmado con la clave oficial
comunidad/<autor>/<id>/
    ficha.json
    <versión>/tema.npt      firmado con la firma de autor (Estudio de Temas)
catalogo.json               lo arma GitHub solo: no se edita a mano
tools/armar_catalogo.py     revisa los temas y arma el catálogo
```

- `<id>` y `<autor>`: minúsculas, números y guiones (por ejemplo `dos-mares`).
- `<versión>`: la misma que tiene el tema por dentro (`1.0`, `1.2`…). Cada versión va en su propia
  carpeta y nunca se reemplaza: así la app no mezcla archivos viejos y nuevos.

## Publicar o actualizar un tema oficial

1. Exporta el tema desde el Estudio de Temas (con la clave oficial).
2. Cópialo como `oficiales/<id>/<versión>/tema.npt` (y, si quieres, crea o edita `ficha.json`).
3. Súbelo a `main`. GitHub revisa el tema y actualiza `catalogo.json` solo.

Si algo está mal (firma, versión, tamaño, nombre repetido), la revisión falla y dice qué corregir.

## Temas de la comunidad

Pasan por la aprobación de OkumaWsX antes de publicarse. La forma de enviarlos (canal de Discord y
normas) se definirá más adelante.

## Seguridad

- El sello **Oficial** o **Comunidad** y el **autor** salen de la **firma** del archivo, nunca de la
  carpeta ni de la ficha: nadie puede hacer pasar un tema por oficial ni usar el nombre de otra persona.
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

## `catalogo.json` (formato 1)

Cada tema trae: `id`, `origen` (`oficial`/`comunidad`), `nombre`, `autor`, `huella_autor`, `version`,
`fecha`, `descripcion`, `etiquetas`, `requiere_app`, `archivo`, `sha256`, `tamano`, `estilo`
(`oscuro`/`claro`), `color` (del acento), `colores` (para la miniatura) y `extras`
(`imagenes`, `animado`, `transparencia`, `degradado`). La app ignora los campos que no conoce.
