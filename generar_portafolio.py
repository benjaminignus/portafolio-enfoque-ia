"""Genera las dos salidas del portafolio a partir de una sola definicion de tarjetas.

  - HTML de escritorio (abre las apps en localhost): se actualiza el existente.
  - PDF para ensenar con videos: una ficha por tarjeta, con un boton que enlaza
    al video por nombre fijo (taller.mp4, clinicas.mp4...) en la misma carpeta
    que el PDF.

Las 4 tarjetas originales se leen del propio HTML (texto e imagenes). Obra Clara
y Automatizacion de WhatsApp se definen aqui; sus fotos se leen de --imagenes:
obra-1.jpg, obra-2.jpg, whatsapp-1.jpg y (opcional) whatsapp-2.jpg.

Uso:
    python generar_portafolio.py --imagenes D:\\Temp\\claude\\portafolio-imgs
    python generar_portafolio.py --imagenes DIR --html-salida X.html --pdf-salida X.pdf
    python generar_portafolio.py --imagenes DIR --copiar-videos
"""
import argparse
import base64
import html as htmlmod
import io
import re
import shutil
import sys
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HTML_ESCRITORIO = Path(r'C:\Users\Karl\Desktop\PORTAFOLIO\portafolio-enfoque-ia_1.html')
PDF_SALIDA = Path(r'D:\claude\portafolio\movil\Portafolio ENFOQUE IA.pdf')

# Color principal y tinte de cada tarjeta (los mismos que usa el CSS del HTML).
COLORES = {
    'taller': ('#e8590c', '#fff1e6'),
    'circulos': ('#1f9d55', '#e6f6ec'),
    'asesorias': ('#2457d6', '#e8eefc'),
    'clinicas': ('#7c3aed', '#f0e9fd'),
    'obra': ('#0f766e', '#e0f2f1'),
    'whatsapp': ('#c2255c', '#fde8ef'),
}
COLORES_OSCURO = {
    'obra': ('#2dd4bf', '#10282a'),
    'whatsapp': ('#ff7aa8', '#2e1522'),
}

# Video de cada tarjeta (nombre fijo junto al PDF) y de donde copiarlo.
VIDEO = {
    'taller': 'taller.mp4',
    'circulos': 'circulos.mp4',
    'asesorias': 'asesorias.mp4',
    'clinicas': 'clinicas.mp4',
    'obra': 'obra-clara.mp4',
    'whatsapp': 'whatsapp.mp4',
}
VIDEO_ORIGEN = {
    'taller.mp4': r'D:\claude\portafolio\app_taller\demo\video\TalleresRuiz_demo_subtitulado.mp4',
    'clinicas.mp4': r'D:\claude\portafolio\AppClinica\demo\video\AppClinica_demo_subtitulado.mp4',
    'obra-clara.mp4': r'D:\claude\portafolio\App-Obra-Clara\demo\video\ObraClara_demo_subtitulado.mp4',
}

# Aplicacion publicada de cada tarjeta: boton «Ver app» junto a «Ver demo» (sin entrada = sin boton).
APP_URL = {
    'taller': 'https://app-taller-beta.vercel.app',
    'clinicas': 'https://app-clinicas-enfoque-ia.vercel.app',
    'obra': 'https://appobraclara.vercel.app/#/resumen',
}

# Tarjetas nuevas (las 4 originales se leen del HTML).
NUEVAS = [
    {
        'id': 'obra',
        'titulo': 'Obra Clara',
        'usuario': 'empresas de reformas y construcción: jefes de obra y encargados que '
                   'controlan el desarrollo de cada obra y sus trabajos extra.',
        'fotos': ['obra-1.jpg', 'obra-2.jpg'],
        'alts': ['Jefe de obra revisando los planos en una tablet dentro de una vivienda en construcción',
                 'Operario colocando azulejos en la cocina de una vivienda en reforma'],
        'boton': 'Acceder a la aplicación',
    },
    {
        'id': 'whatsapp',
        'titulo': 'Automatización de WhatsApp',
        'usuario': 'negocios y equipos que atienden a sus clientes por WhatsApp y quieren '
                   'responder, avisar y gestionar citas de forma automática.',
        'fotos': ['whatsapp-1.jpg', 'whatsapp-2.jpg'],
        'alts': ['Dueña de una tienda sonriendo mientras mira una conversación en su móvil',
                 'Mano sosteniendo un móvil con una conversación de mensajes'],
        'boton': None,  # aun no hay aplicacion: boton «Próximamente»
    },
]


# ----------------------------------------------------------------- imagenes
def preparar(datos: bytes) -> bytes:
    """Recorta al centro a 4:3 y deja un JPEG de 960x720 (como las demas tarjetas)."""
    im = Image.open(io.BytesIO(datos)).convert('RGB')
    w, h = im.size
    objetivo = 4 / 3
    if w / h > objetivo:
        nw = round(h * objetivo)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w / objetivo)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = im.resize((960, 720), Image.LANCZOS)
    salida = io.BytesIO()
    im.save(salida, 'JPEG', quality=82, optimize=True)
    return salida.getvalue()


def cargar_fotos(carpeta: Path, nombres):
    fotos = []
    for i, nombre in enumerate(nombres):
        ruta = carpeta / nombre
        if ruta.exists():
            fotos.append((nombre, preparar(ruta.read_bytes())))
        elif i == 0:
            sys.exit(f'Falta la foto obligatoria {ruta}')
    return fotos


# --------------------------------------------------------------------- HTML
RE_ARTICULO = re.compile(r'\n    <article class="cell (\w+)">.*?</article>\n', re.S)


def leer_tarjetas_originales(texto):
    tarjetas = []
    for m in re.finditer(r'<article class="cell (\w+)">(.*?)</article>', texto, re.S):
        tid, cuerpo = m.group(1), m.group(2)
        titulo = htmlmod.unescape(re.search(r'<h2>(.*?)</h2>', cuerpo, re.S).group(1).strip())
        usuario = re.search(r'<p class="user"><strong>Usuario:</strong>\s*(.*?)</p>', cuerpo, re.S)
        imgs = re.findall(r'<img src="data:image/jpeg;base64,([^"]+)"', cuerpo)
        tarjetas.append({
            'id': tid,
            'titulo': titulo,
            'usuario': htmlmod.unescape(usuario.group(1).strip()) if usuario else '',
            'imgs': [base64.b64decode(b) for b in imgs],
        })
    return tarjetas


def articulo_html(t):
    slides = '\n'.join(
        f'          <div class="slide"><img src="data:image/jpeg;base64,'
        f'{base64.b64encode(datos).decode()}" alt="{htmlmod.escape(alt)}"></div>'
        for datos, alt in zip(t['imgs'], t['alts'])
    )
    if t.get('boton'):
        boton = f'<a class="access" href="#" data-app="{t["id"]}">{t["boton"]}</a>'
    else:
        boton = (f'<a class="access pronto" href="#" data-app="{t["id"]}" '
                 f'aria-disabled="true">Próximamente</a>')
    titulo = htmlmod.escape(t['titulo'])
    return (
        f'\n    <article class="cell {t["id"]}">\n'
        f'      <div class="cell-head"><h2>{titulo}</h2></div>\n'
        f'      <div class="carousel" data-label="{titulo}">\n'
        f'        <div class="track">\n{slides}\n        </div>\n'
        f'      </div>\n'
        f'      <div class="cell-body">\n'
        f'        <p class="user"><strong>Usuario:</strong> {htmlmod.escape(t["usuario"])}</p>\n'
        f'        {boton}\n'
        f'      </div>\n'
        f'    </article>\n'
    )


ICONO_APP = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
             '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>')
CSS_VER_APP = (
    '.acciones{margin-top:auto;display:flex;flex-wrap:wrap;gap:10px}\n'
    '.estado + .acciones{margin-top:0}\n'
    '.acciones .access{margin-top:0;align-self:auto}\n'
    '.access-app{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;'
    'padding:10px 22px;border-radius:12px;border:2px solid var(--c);background:transparent;color:var(--ink);'
    'font:inherit;font-weight:700;text-decoration:none}\n'
    '.access-app svg{width:18px;height:18px;flex:none}\n'
    '.access-app:hover{background:var(--tint)}\n'
    '@media (max-width:820px){.acciones{flex-direction:column}.acciones .access,.access-app{align-self:stretch}}\n'
)


def acciones_movil(tid):
    """Botones de una tarjeta movil: «Ver demo» y, si hay app publicada, «Ver app»."""
    boton = f'<button class="access" type="button" data-app="{tid}" disabled>▶ Ver demo</button>'
    url = APP_URL.get(tid)
    if not url:
        return f'        {boton}\n'
    return (f'        <div class="acciones">\n'
            f'          {boton}\n'
            f'          <a class="access-app" href="{url}" target="_blank" rel="noopener">'
            f'{ICONO_APP} Ver app</a>\n'
            f'        </div>\n')


def anadir_ver_app(texto):
    """Pone «Ver app» junto a «Ver demo» en las tarjetas con app publicada (idempotente)."""
    for tid in APP_URL:
        viejo = f'\n        <button class="access" type="button" data-app="{tid}" disabled>▶ Ver demo</button>\n'
        if viejo in texto:
            texto = texto.replace(viejo, '\n' + acciones_movil(tid), 1)
    if '.acciones{' not in texto:
        texto = sustituir(texto, '.access:hover{filter:brightness(1.08)}\n',
                          '.access:hover{filter:brightness(1.08)}\n' + CSS_VER_APP, 'estilo del boton (movil)')
    return texto


def articulo_movil(t):
    """Tarjeta de la pagina movil: igual que la de escritorio, pero con estado del
    video y boton «Ver demo» (se activa sola si el .mp4 esta junto a la pagina)."""
    slides = '\n'.join(
        f'          <div class="slide"><img src="data:image/jpeg;base64,'
        f'{base64.b64encode(datos).decode()}" alt="{htmlmod.escape(alt)}"></div>'
        for datos, alt in zip(t['imgs'], t['alts'])
    )
    titulo = htmlmod.escape(t['titulo'])
    return (
        f'\n    <article class="cell {t["id"]}">\n'
        f'      <div class="cell-head"><h2>{titulo}</h2></div>\n'
        f'      <div class="carousel" data-label="{titulo}">\n'
        f'        <div class="track">\n{slides}\n        </div>\n'
        f'      </div>\n'
        f'      <div class="cell-body">\n'
        f'        <p class="user"><strong>Usuario:</strong> {htmlmod.escape(t["usuario"])}</p>\n'
        f'        <p class="estado" data-estado="comprobando" aria-live="polite">'
        f'<span class="punto" aria-hidden="true"></span>'
        f'<span class="txt">Comprobando vídeo…</span></p>\n'
        f'{acciones_movil(t["id"])}'
        f'        <p class="aviso" role="status" hidden></p>\n'
        f'      </div>\n'
        f'    </article>\n'
    )


def actualizar_movil(texto, nuevas):
    texto = re.sub(r'[ \t]*\[Texto provisional\]', '', texto)
    texto = RE_ARTICULO.sub(
        lambda m: '\n' if m.group(1) in ('obra', 'whatsapp') else m.group(0), texto)
    bloque = ''.join(articulo_movil(t) for t in nuevas)
    texto = sustituir(texto, '\n  </div>\n</section>', bloque + '\n  </div>\n</section>',
                      'cierre de la rejilla (movil)')
    if '.cell.obra{' not in texto:
        c, d = COLORES['obra'], COLORES['whatsapp']
        texto = sustituir(
            texto, '.cell.clinicas{--c:#7c3aed;--tint:#f0e9fd}',
            '.cell.clinicas{--c:#7c3aed;--tint:#f0e9fd}\n'
            f'.cell.obra{{--c:{c[0]};--tint:{c[1]}}}\n'
            f'.cell.whatsapp{{--c:{d[0]};--tint:{d[1]}}}', 'color de Clinicas (movil)')
        co, do = COLORES_OSCURO['obra'], COLORES_OSCURO['whatsapp']
        texto = sustituir(
            texto, '[data-theme="dark"] .cell.clinicas{--c:#b48cff;--tint:#231a38}',
            '[data-theme="dark"] .cell.clinicas{--c:#b48cff;--tint:#231a38}\n'
            f'[data-theme="dark"] .cell.obra{{--c:{co[0]};--tint:{co[1]}}}\n'
            f'[data-theme="dark"] .cell.whatsapp{{--c:{do[0]};--tint:{do[1]}}}',
            'color oscuro de Clinicas (movil)')
    texto = texto.replace(
        'Cuatro aplicaciones pensadas para quien las usa cada día. Elige una para ver su demo en vídeo.',
        'Seis propuestas pensadas para quien las usa cada día. Elige una para ver su demo en vídeo.')
    if 'obra:      { file:' not in texto:
        texto = sustituir(
            texto, '  clinicas:  { file:"clinicas.mp4" }\n};',
            '  clinicas:  { file:"clinicas.mp4" },\n'
            '  obra:      { file:"obra-clara.mp4" },\n'
            '  whatsapp:  { file:"whatsapp.mp4", proximamente:true }\n};', 'DEMOS (movil)')
    # En internet no hay «Descargas»: el aviso de video ausente es mas corto.
    texto = texto.replace(
        '"». Tiene que estar en la misma carpeta que esta página (Descargas) y con ese nombre exacto."',
        '(location.protocol.indexOf("http") === 0 ? "» junto a esta página." : '
        '"». Tiene que estar en la misma carpeta que esta página (Descargas) y con ese nombre exacto.")')
    if 'if(n<2) return;' not in texto:
        texto = sustituir(texto, '  let i=0;\n  const prev=',
                          '  if(n<2) return;   // una sola foto: sin flechas ni puntos\n'
                          '  let i=0;\n  const prev=', 'carrusel (movil)')
    return anadir_ver_app(texto)


def escribir_movil_y_web(movil: Path, web_dir: Path, nuevas):
    crudo = movil.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    crlf = '\r\n' in texto
    texto = actualizar_movil(texto.replace('\r\n', '\n'), nuevas)
    salida = texto.replace('\n', '\r\n') if crlf else texto
    movil.write_bytes((b'\xef\xbb\xbf' if bom else b'') + salida.encode('utf-8'))

    # Carpeta del sitio: pagina + los videos que existan + .nojekyll (GitHub Pages).
    web_dir.mkdir(parents=True, exist_ok=True)
    (web_dir / 'index.html').write_bytes(texto.encode('utf-8'))
    (web_dir / '.nojekyll').write_text('')
    publicados = []
    for nombre in VIDEO.values():
        origen = movil.parent / nombre
        if origen.exists() and origen.stat().st_size > 0:
            shutil.copy2(origen, web_dir / nombre)
            publicados.append(nombre)
    return publicados


def sustituir(texto, viejo, nuevo, descripcion):
    if viejo not in texto:
        sys.exit(f'No encuentro en el HTML: {descripcion}')
    return texto.replace(viejo, nuevo, 1)


def actualizar_html(texto, nuevas):
    # 1. Fuera el texto provisional.
    texto = re.sub(r'[ \t]*\[Texto provisional\]', '', texto)

    # 2. Si ya estaban las tarjetas nuevas (nueva ejecucion), se quitan y se rehacen.
    def quitar(m):
        return '\n' if m.group(1) in ('obra', 'whatsapp') else m.group(0)
    texto = RE_ARTICULO.sub(quitar, texto)

    # 3. Tarjetas nuevas al final de la rejilla.
    bloque = ''.join(articulo_html(t) for t in nuevas)
    texto = sustituir(texto, '\n  </div>\n</section>', bloque + '\n  </div>\n</section>',
                      'cierre de la rejilla')

    # 4. Estilos de color (claro y oscuro) y boton «Próximamente».
    if '.cell.obra{' not in texto:
        c, d = COLORES['obra'], COLORES['whatsapp']
        texto = sustituir(
            texto, '.cell.clinicas{--c:#7c3aed;--tint:#f0e9fd}',
            '.cell.clinicas{--c:#7c3aed;--tint:#f0e9fd}\n'
            f'.cell.obra{{--c:{c[0]};--tint:{c[1]}}}\n'
            f'.cell.whatsapp{{--c:{d[0]};--tint:{d[1]}}}', 'color de Clinicas')
        co, do = COLORES_OSCURO['obra'], COLORES_OSCURO['whatsapp']
        texto = sustituir(
            texto, '[data-theme="dark"] .cell.clinicas{--c:#b48cff;--tint:#231a38}',
            '[data-theme="dark"] .cell.clinicas{--c:#b48cff;--tint:#231a38}\n'
            f'[data-theme="dark"] .cell.obra{{--c:{co[0]};--tint:{co[1]}}}\n'
            f'[data-theme="dark"] .cell.whatsapp{{--c:{do[0]};--tint:{do[1]}}}',
            'color oscuro de Clinicas')
    if '.access.pronto' not in texto:
        texto = sustituir(
            texto, '.access:hover{filter:brightness(1.08)}',
            '.access:hover{filter:brightness(1.08)}\n'
            '.access.pronto{background:var(--line);color:var(--muted);cursor:default;'
            'pointer-events:none;filter:none}\n'
            '[data-theme="dark"] .access.pronto{color:var(--muted)}',
            'estilo del boton')

    # 5. Texto de introduccion.
    texto = texto.replace('Cuatro aplicaciones pensadas para quien las usa cada día.',
                          'Seis propuestas pensadas para quien las usa cada día.')

    # 6. Enlaces de las apps nuevas.
    if 'obra:"http://localhost:5681"' not in texto:
        texto = sustituir(texto, 'clinicas:"http://localhost:5680" }',
                          'clinicas:"http://localhost:5680", obra:"http://localhost:5681", whatsapp:"#" }',
                          'APP_LINKS')
        texto = sustituir(texto, 'clinicas:"AppClinica (demo)" }',
                          'clinicas:"AppClinica (demo)", obra:"Obra Clara (demo)", whatsapp:"" }',
                          'APP_ACCESOS')

    # 7. Una sola foto: sin flechas ni puntos.
    if 'if(n<2) return;' not in texto:
        texto = sustituir(texto, '  let i=0;\n  const prev=',
                          '  if(n<2) return;   // una sola foto: sin flechas ni puntos\n'
                          '  let i=0;\n  const prev=', 'carrusel')
    return texto


def escribir_html(entrada: Path, salida: Path, nuevas):
    crudo = entrada.read_bytes()
    bom = crudo.startswith(b'\xef\xbb\xbf')
    texto = crudo.decode('utf-8-sig')
    crlf = '\r\n' in texto
    texto = texto.replace('\r\n', '\n')
    texto = actualizar_html(texto, nuevas)
    if crlf:
        texto = texto.replace('\n', '\r\n')
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes((b'\xef\xbb\xbf' if bom else b'') + texto.encode('utf-8'))
    return texto.replace('\r\n', '\n')


# ---------------------------------------------------------------------- PDF
W, H = A4
M = 40
INK, MUTED, LINE, BG = HexColor('#16181d'), HexColor('#5b616d'), HexColor('#dfe2e8'), HexColor('#f6f7f9')


def fuentes():
    try:
        pdfmetrics.registerFont(TTFont('UI', r'C:\Windows\Fonts\segoeui.ttf'))
        pdfmetrics.registerFont(TTFont('UI-B', r'C:\Windows\Fonts\segoeuib.ttf'))
        return 'UI', 'UI-B'
    except Exception:
        return 'Helvetica', 'Helvetica-Bold'


def triangulo(c, x, y, tam, color):
    """Triangulo de «reproducir» con el vertice izquierdo-inferior en (x, y)."""
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x, y)
    p.lineTo(x, y + tam)
    p.lineTo(x + tam * 0.9, y + tam / 2)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


ANCHO_DEMO_CON_APP = 300   # ancho del boton «Ver demo» cuando la ficha tiene tambien «Ver app»


def caja_demo(tid):
    """(x, ancho) del boton de video de una ficha: entero, o a la izquierda si hay «Ver app»."""
    return M, (ANCHO_DEMO_CON_APP if tid in APP_URL else W - 2 * M)


def flecha(c, x, y, tam, color):
    """Flecha diagonal hacia arriba a la derecha (icono de enlace externo)."""
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(2.2)
    c.setLineCap(1)
    c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(x, y)
    p.lineTo(x + tam, y + tam)
    p.moveTo(x + tam * 0.3, y + tam)
    p.lineTo(x + tam, y + tam)
    p.lineTo(x + tam, y + tam * 0.3)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def pdf_boton_app(c, B, tid, color, by, bh):
    """Boton «Ver app» (con contorno del color de la tarjeta) a la derecha del de video."""
    ax = M + ANCHO_DEMO_CON_APP + 12
    aw = W - M - ax
    c.setFillColor(white)
    c.setStrokeColor(color)
    c.setLineWidth(2)
    c.roundRect(ax, by, aw, bh, 12, stroke=1, fill=1)
    c.setLineWidth(1)
    etiqueta = 'Ver app'
    c.setFont(B, 16)
    ancho = pdfmetrics.stringWidth(etiqueta, B, 16)
    x0 = ax + (aw - (ancho + 26)) / 2
    flecha(c, x0, by + bh / 2 - 6, 12, INK)
    c.setFillColor(INK)
    c.drawString(x0 + 26, by + bh / 2 - 5.5, etiqueta)
    c.linkURL(APP_URL[tid], (ax, by, ax + aw, by + bh), relative=0, thickness=0)


def parrafo(c, texto, fuente, tam, ancho, x, y, interlineado, color):
    c.setFillColor(color)
    c.setFont(fuente, tam)
    for linea in simpleSplit(texto, fuente, tam, ancho):
        c.drawString(x, y, linea)
        y -= interlineado
    return y


def pdf_portada(c, R, B, tarjetas, hay_video, incrustado=False):
    c.bookmarkPage('portada')
    c.setFillColor(BG)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    y = H - M - 12
    c.setFillColor(INK)
    c.setFont(B, 15)
    c.drawString(M, y, 'ENFOQUE IA')
    c.setFillColor(MUTED)
    c.setFont(R, 15)
    c.drawString(M + pdfmetrics.stringWidth('ENFOQUE IA ', B, 15), y, '· Portafolio')
    y -= 64
    y = parrafo(c, 'Aplicaciones de IA por sector', B, 31, W - 2 * M, M, y, 38, INK)
    y -= 4
    y = parrafo(c, 'Seis propuestas pensadas para quien las usa cada día. '
                   'Pulsa una para ver su ficha y su demo en vídeo.', R, 13.5, W - 2 * M, M, y, 19, MUTED)
    y -= 18
    alto, hueco = 74, 11
    for t in tarjetas:
        base = y - alto
        color = HexColor(COLORES[t['id']][0])
        c.setFillColor(white)
        c.setStrokeColor(LINE)
        c.roundRect(M, base, W - 2 * M, alto, 14, stroke=1, fill=1)
        c.setFillColor(color)
        c.roundRect(M, base, 9, alto, 4.5, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont(B, 17)
        c.drawString(M + 26, base + alto - 31, t['titulo'])
        if hay_video(t['id']):
            triangulo(c, M + 26, base + 15, 11, color)
            c.setFillColor(color)
            c.setFont(B, 12)
            c.drawString(M + 44, base + 15, 'Demo en vídeo')
        else:
            c.setFillColor(MUTED)
            c.setFont(R, 12)
            c.drawString(M + 26, base + 15, 'Demo próximamente')
        c.setFillColor(MUTED)
        c.setFont(R, 20)
        c.drawRightString(W - M - 18, base + alto / 2 - 7, '›')
        c.linkRect('', t['id'], (M, base, W - M, y), relative=0)
        y = base - hueco
    if incrustado:
        aviso = ('Cada ficha lleva su vídeo incrustado en este PDF: toca el clip de su botón. '
                 'Hace falta un visor de PDF con soporte de adjuntos (p. ej. Adobe Acrobat Reader '
                 'o Xodo); si abre el navegador o no responde, el visor no los admite.')
    else:
        aviso = ('Los vídeos se abren por su nombre fijo (taller.mp4, clinicas.mp4, circulos.mp4, '
                 'asesorias.mp4, obra-clara.mp4 y whatsapp.mp4): deja los .mp4 en la misma '
                 'carpeta que este PDF.')
    y = parrafo(c, aviso, R, 10.5, W - 2 * M, M, y - 10, 14.5, MUTED)
    c.showPage()


def pdf_tarjeta(c, R, B, t, n, total, video_ok, incrustado=False):
    color, tinte = (HexColor(x) for x in COLORES[t['id']])
    c.bookmarkPage(t['id'])
    # Cabecera: tinte con borde inferior del color de la tarjeta (como en la web).
    alto_cab = 92
    c.setFillColor(tinte)
    c.rect(0, H - alto_cab, W, alto_cab, stroke=0, fill=1)
    c.setFillColor(color)
    c.rect(0, H - alto_cab - 4, W, 4, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont(B, 26)
    c.drawString(M, H - alto_cab + 34, t['titulo'])
    c.setFillColor(MUTED)
    c.setFont(R, 11)
    c.drawString(M, H - alto_cab + 66, 'ENFOQUE IA · Portafolio')
    c.drawRightString(W - M, H - alto_cab + 66, '‹ Índice')
    c.linkRect('', 'portada', (W - M - 70, H - alto_cab + 56, W - M, H - alto_cab + 82), relative=0)

    # Fotos (4:3), centradas; con una sola, mas grande.
    imgs = t['imgs']
    iw = 340 if len(imgs) > 1 else 440
    ih = iw * 3 / 4
    y = H - alto_cab - 4 - 24
    for datos in imgs:
        x = (W - iw) / 2
        c.saveState()
        p = c.beginPath()
        p.roundRect(x, y - ih, iw, ih, 12)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(ImageReader(io.BytesIO(datos)), x, y - ih, iw, ih)
        c.restoreState()
        c.setStrokeColor(LINE)
        c.roundRect(x, y - ih, iw, ih, 12, stroke=1, fill=0)
        y -= ih + 14

    # Usuario.
    y -= 10
    c.setFillColor(INK)
    c.setFont(B, 13.5)
    c.drawString(M, y, 'Usuario:')
    y = parrafo(c, t['usuario'], R, 13.5, W - 2 * M - 62, M + 62, y, 19, MUTED)

    # Boton de video (o aviso de que aun no hay).
    bh = 52
    by = 74
    bx, bw = caja_demo(t['id'])
    if video_ok:
        c.setFillColor(color)
        c.roundRect(bx, by, bw, bh, 12, stroke=0, fill=1)
        etiqueta = 'Ver demo: toca el clip' if incrustado else 'Ver demo en vídeo'
        c.setFont(B, 16)
        ancho = pdfmetrics.stringWidth(etiqueta, B, 16)
        x0 = bx + (bw - (ancho + 30)) / 2
        triangulo(c, x0, by + bh / 2 - 8, 16, white)
        c.setFillColor(white)
        c.drawString(x0 + 30, by + bh / 2 - 5.5, etiqueta)
        if incrustado:
            # El video va dentro del PDF: sin enlace a archivo (apuntaria a un archivo
            # que no existe junto al PDF y abriria el navegador con un error).
            nota = (f'Vídeo incrustado ({VIDEO[t["id"]]}): toca el clip. '
                    f'Si no responde, tu visor de PDF no admite adjuntos.')
        else:
            c.linkURL(VIDEO[t['id']], (bx, by, bx + bw, by + bh), relative=0, thickness=0)
            nota = f'Vídeo: {VIDEO[t["id"]]} (en la misma carpeta que este PDF)'
    else:
        c.setFillColor(HexColor('#eceef2'))
        c.roundRect(bx, by, bw, bh, 12, stroke=0, fill=1)
        c.setFillColor(MUTED)
        c.setFont(B, 16)
        c.drawCentredString(bx + bw / 2, by + bh / 2 - 5.5, 'Demo próximamente')
        nota = f'Se activará al dejar {VIDEO[t["id"]]} junto a este PDF y regenerarlo'
    if t['id'] in APP_URL:
        pdf_boton_app(c, B, t['id'], color, by, bh)
    c.setFillColor(MUTED)
    c.setFont(R, 10)
    c.drawString(M, 48, nota)
    c.drawRightString(W - M, 48, f'{n} / {total}')
    c.showPage()


def escribir_pdf(salida: Path, tarjetas, carpeta_videos: Path, incrustado=False):
    R, B = fuentes()
    salida.parent.mkdir(parents=True, exist_ok=True)

    def hay_video(tid):
        return (carpeta_videos / VIDEO[tid]).exists()

    c = canvas.Canvas(str(salida), pagesize=A4)
    c.setTitle('Portafolio · Enfoque IA')
    c.setAuthor('Enfoque IA')
    c.setSubject('Aplicaciones de IA por sector: fichas y demos en vídeo')
    pdf_portada(c, R, B, tarjetas, hay_video, incrustado)
    for i, t in enumerate(tarjetas, start=2):
        pdf_tarjeta(c, R, B, t, i, len(tarjetas) + 1, hay_video(t['id']), incrustado)
    c.save()
    if incrustado:
        incrustar_videos(salida, tarjetas, carpeta_videos)


def incrustar_videos(pdf: Path, tarjetas, carpeta_videos: Path):
    """Mete cada video dentro del PDF: adjunto del documento (panel de adjuntos del
    visor) y una anotacion de archivo adjunto (el clip) sobre el boton de su ficha.
    Las dos comparten el mismo flujo de datos, asi que el video no se duplica."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf))
    for i, t in enumerate(tarjetas, start=1):  # pagina 0 = portada
        nombre = VIDEO[t['id']]
        ruta = carpeta_videos / nombre
        if not ruta.exists() or ruta.stat().st_size == 0:
            continue
        doc.embfile_add(nombre, ruta.read_bytes(), filename=nombre, ufilename=nombre,
                        desc=t['titulo'])
        # El adjunto recien creado: PyMuPDF guarda su descriptor en linea dentro del
        # catalogo (/Names /EmbeddedFiles) y apunta al flujo de datos con /EF << /F n 0 R >>.
        catalogo = doc.xref_get_key(doc.pdf_catalog(), 'Names')[1]
        m = re.search(r'/UF\(' + re.escape(nombre) + r'\)[^>]*?/EF<</F (\d+) 0 R', catalogo) or \
            re.search(r'/EF<</F (\d+) 0 R>>/F\(' + re.escape(nombre) + r'\)', catalogo)
        if not m:
            sys.exit(f'No encuentro el flujo del adjunto {nombre} recien incrustado')
        flujo = int(m.group(1))
        filespec = (f'<</Type/Filespec/F({nombre})/UF({nombre})/EF<</F {flujo} 0 R>>>>')
        # Clip a la derecha del boton de video (y=74..126 en el PDF; ancho segun caja_demo).
        # MuPDF dibuja el icono a 20x20 pt: se centra verticalmente en el boton.
        lado = 20
        bx, bw = caja_demo(t['id'])
        x1 = bx + bw - 12 - lado
        y1 = 74 + (52 - lado) / 2
        pagina = doc[i]
        punto = fitz.Point(x1, H - (y1 + lado))
        anot = pagina.add_file_annot(punto, b'0', nombre, desc=t['titulo'], icon='Paperclip')
        doc.xref_set_key(anot.xref, 'FS', filespec)
    tmp = pdf.with_suffix('.tmp.pdf')
    doc.save(str(tmp), garbage=4, deflate=True)
    doc.close()
    tmp.replace(pdf)


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument('--imagenes', required=True, type=Path, help='carpeta con obra-1.jpg, obra-2.jpg, whatsapp-1.jpg...')
    ap.add_argument('--html-entrada', type=Path, default=HTML_ESCRITORIO)
    ap.add_argument('--html-salida', type=Path, default=None, help='por defecto, el mismo HTML de entrada')
    ap.add_argument('--pdf-salida', type=Path, default=PDF_SALIDA)
    ap.add_argument('--copiar-videos', action='store_true',
                    help='copia los videos subtitulados disponibles junto al PDF con nombre fijo')
    ap.add_argument('--pdf-incrustado', type=Path, default=None,
                    help='genera ademas un PDF con los videos incrustados (pesa decenas de MB)')
    ap.add_argument('--web-dir', type=Path, default=None,
                    help='actualiza la pagina movil con las 6 tarjetas y monta en esta carpeta '
                         'el sitio para internet (index.html + videos)')
    ap.add_argument('--movil-html', type=Path,
                    default=Path(r'D:\claude\portafolio\movil\portafolio-movil.html'))
    a = ap.parse_args()
    html_salida = a.html_salida or a.html_entrada

    # Tarjetas nuevas con sus fotos.
    nuevas = []
    for n in NUEVAS:
        fotos = cargar_fotos(a.imagenes, n['fotos'])
        t = dict(n)
        t['imgs'] = [d for _, d in fotos]
        t['alts'] = n['alts'][:len(fotos)]
        nuevas.append(t)

    # HTML (y de el, las tarjetas originales ya sin texto provisional).
    texto = escribir_html(a.html_entrada, html_salida, nuevas)
    originales = leer_tarjetas_originales(
        RE_ARTICULO.sub(lambda m: '\n' if m.group(1) in ('obra', 'whatsapp') else m.group(0), texto))
    todas = originales + nuevas

    # Videos junto al PDF.
    carpeta = a.pdf_salida.parent
    if a.copiar_videos:
        carpeta.mkdir(parents=True, exist_ok=True)
        for nombre, origen in VIDEO_ORIGEN.items():
            destino = carpeta / nombre
            if Path(origen).exists() and not destino.exists():
                shutil.copy2(origen, destino)
                print(f'copiado {nombre}')

    escribir_pdf(a.pdf_salida, todas, carpeta)
    if a.pdf_incrustado:
        escribir_pdf(a.pdf_incrustado, todas, carpeta, incrustado=True)
    if a.web_dir:
        publicados = escribir_movil_y_web(a.movil_html, a.web_dir, nuevas)
        print(f'Movil actualizado: {a.movil_html}')
        print(f'Sitio web: {a.web_dir} (videos: {", ".join(publicados)})')
    print(f'HTML: {html_salida}')
    print(f'PDF:  {a.pdf_salida}')
    if a.pdf_incrustado:
        print(f'PDF con videos incrustados: {a.pdf_incrustado} '
              f'({a.pdf_incrustado.stat().st_size / 1048576:.1f} MB)')
    for t in todas:
        print(f'  {t["id"]:<10} {len(t["imgs"])} foto(s)  video={VIDEO[t["id"]]} '
              f'({"si" if (carpeta / VIDEO[t["id"]]).exists() else "no"})')


if __name__ == '__main__':
    main()
