# Portafolio en el móvil (demos en vídeo)

`portafolio-movil.html` es el menú del portafolio sin servidores: cada tarjeta reproduce el vídeo de su demo.
Contraseña de entrada: la misma del menú de escritorio (`PASSWORD` al principio del `<script>`).

## Archivos que deben estar en la carpeta Descargas del móvil

Todos en la **misma carpeta**, con estos nombres exactos (minúsculas):

| Archivo | Tarjeta | Origen en el PC (versión con subtítulos grabados) |
| --- | --- | --- |
| `portafolio-movil.html` | — | `D:\claude\portafolio\movil\portafolio-movil.html` |
| `taller.mp4` | Taller de coches | `D:\claude\portafolio\app_taller\demo\video\TalleresRuiz_demo_subtitulado.mp4` |
| `clinicas.mp4` | Clínicas | `D:\claude\portafolio\AppClinica\demo\video\AppClinica_demo_subtitulado.mp4` |
| `circulos.mp4` | Círculos de confianza | (sin vídeo todavía → «Demo próximamente») |
| `asesorias.mp4` | Asesorías | (sin vídeo todavía → «Demo próximamente») |

- Envía la versión `_subtitulado`: WhatsApp recomprime y **elimina** las pistas de subtítulos, así que solo valen los subtítulos grabados en la imagen.
- WhatsApp renombra los vídeos (`VID-…-WA0001.mp4`): **renómbralos en el móvil** a `taller.mp4` y `clinicas.mp4` (si Android añade `(1)`, el nombre ya no coincide).
- Para activar una demo nueva (Círculos o Asesorías) basta con dejar su `.mp4` con ese nombre junto a la página; la tarjeta se activa sola al volver a ella, sin tocar el HTML.
- La página también se puede enviar por WhatsApp (como documento) o copiar por cable.

## Cómo abrirla en Android (Chrome)

No la abras tocándola en el gestor de archivos ni desde WhatsApp: Chrome la abre como `content://` y no puede leer los vídeos de al lado. Escribe en la barra de direcciones de Chrome:

```
file:///storage/emulated/0/Download/portafolio-movil.html
```

(Puedes guardarla como marcador o «Añadir a pantalla de inicio».)

## Versión en PDF (`Portafolio ENFOQUE IA.pdf`)

Una portada con el índice y una ficha por tarjeta (fotos, usuario, botón «Ver demo · N min» y, si hay app publicada, «Ver app»).
«Ver demo» es un enlace **relativo** al vídeo, así que los `.mp4` deben estar en la **misma carpeta que el PDF** con estos nombres fijos:
`taller.mp4`, `clinicas.mp4`, `obra-clara.mp4`, `circulos.mp4`, `asesorias.mp4`, `whatsapp.mp4`.

- Un PDF no puede abrir un selector de archivos: por eso el vídeo se elige por nombre fijo. Los que no existen
  (Círculos, Asesorías, WhatsApp) salen como «Demo próximamente».
- Ya hay copias de `taller.mp4`, `clinicas.mp4` y `obra-clara.mp4` en esta carpeta (versión `_subtitulado`).
- Los enlaces los abre bien el visor de Chrome/Edge en el PC. En el móvil depende del visor de PDF; si no abre el
  vídeo desde el PDF, usa `portafolio-movil.html`.

### PDF con los vídeos incrustados (`Portafolio ENFOQUE IA - videos incrustados.pdf`, ~37 MB)

Mismo contenido, pero cada vídeo va **dentro** del PDF (una sola copia): como adjunto del documento (panel de adjuntos
del visor) y con un clip 📎 sobre el botón de su ficha. Es un solo archivo: no hace falta copiar los `.mp4` ni cuidar nombres.
Está pensado para la tablet, donde el enlace a un archivo local abre Chrome y no VLC: al tocar el clip, el visor entrega el
adjunto a la app asociada a `.mp4` (VLC). Depende del visor: Adobe Acrobat Reader, Xodo y Foxit suelen soportarlo; el visor
integrado de Chrome, probablemente no. Prueba mínima de las 4 variantes en `prueba-tablet\`.

## Publicado en internet (GitHub Pages)

- **URL:** https://benjaminignus.github.io/portafolio-enfoque-ia/ · repo público `benjaminignus/portafolio-enfoque-ia`.
- Es la página móvil con las 6 tarjetas + `taller.mp4`, `clinicas.mp4` y `obra-clara.mp4` (≈ 38 MB). Local: `D:\claude\portafolio\web\`.
- **Es público:** cualquiera con el enlace ve la página y puede bajar los vídeos. La contraseña de la página (`enfoqueia`)
  está en el propio código y no protege los vídeos.
- Actualizar: `python generar_portafolio.py --imagenes D:\Temp\claude\portafolio-imgs --web-dir D:\claude\portafolio\web`
  y luego, en esa carpeta, `git add -A && git commit -m ... && git push` (Pages se republica solo en ~1 min).
- Para activar una demo nueva: deja su `.mp4` con nombre fijo en `movil\`, ejecuta el comando de arriba y sube.
- Commits con identidad `Enfoque IA <…@users.noreply.github.com>` (no se expone el correo personal).

## Regenerar HTML de escritorio y PDF

`generar_portafolio.py` produce las dos salidas a la vez (las 4 tarjetas originales se leen del HTML de escritorio;
Obra Clara y WhatsApp se definen en el script). Fotos de las dos tarjetas nuevas en `D:\Temp\claude\portafolio-imgs`
(`obra-1.jpg`, `obra-2.jpg`, `whatsapp-1.jpg`, `whatsapp-2.jpg`).

```
python generar_portafolio.py --imagenes D:\Temp\claude\portafolio-imgs --copiar-videos
python generar_portafolio.py --imagenes D:\Temp\claude\portafolio-imgs --pdf-incrustado "D:\claude\portafolio\movil\Portafolio ENFOQUE IA - videos incrustados.pdf"
```

Para activar una demo nueva: deja su `.mp4` con el nombre fijo junto al PDF y vuelve a ejecutarlo. El HTML móvil
(`portafolio-movil.html`) es independiente y no lo toca el script.

## Comportamiento

- Cada tarjeta comprueba al cargar si su `.mp4` está junto a la página y, si está, el botón pasa a «🎞 Ver demo · N min» (minutos redondeados). Si falta, el botón dice «Falta el vídeo» y un aviso explica por qué (y si abres la página como `content://`, cómo abrirla bien).
- «Ver demo» abre el vídeo a pantalla completa con controles. La ✕ o el gesto «atrás» del móvil vuelven al menú.
- «Ver app» (Taller, Clínicas y Obra Clara) abre la aplicación publicada en una pestaña nueva; las URL están en `APP_URL` de `generar_portafolio.py`.
- En Círculos de confianza el botón de demo se llama «Demo en móvil» (`ETIQUETA_DEMO`); sin vídeo sale desactivado.
- «Información» (primer botón de cada tarjeta, salvo WhatsApp) hace pasar solas las slides del carrusel: las fotos y, entre
  ellas, slides de texto con el color de la tarjeta y letras grandes (3 s por foto, 5 s por texto). Se detiene al mover la
  página, al pulsar cualquier otro botón o al volver a pulsar «Información». Los textos y sus iconos están en `INFO` de
  `generar_portafolio.py`; los PDF no llevan estas slides (son estáticos).
- Se conservan las imágenes del carrusel y el modo noche del menú de escritorio.
- `index.html` es copia de `portafolio-movil.html` (la usa GitHub Pages): tras cambiar la página, vuelve a copiarla.
