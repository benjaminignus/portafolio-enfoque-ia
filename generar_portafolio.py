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
import subprocess
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
    'clinicas': 'https://app-clinicas-enfoque-ia.vercel.app/entrar',
    'obra': 'https://appobraclara.vercel.app/#/resumen',
    'asesorias': 'https://app-asesorias.vercel.app/acceso',
}

# Acceso de prueba de las apps publicadas que lo necesitan: cuentas de una demo con datos ficticios y
# contrasena publica a proposito (solo las del asesor y el cliente; la del administrador no se publica).
# Salen en la pagina movil («Acceso de prueba») y en la ficha del PDF.
ACCESO_DEMO = {
    'asesorias': {
        'lineas': [('Asesora', 'marta@rierabono.es'), ('Cliente', 'pablo@laespiga.es')],
        'clave': 'enfoqueia',
    },
}

# Texto de «Usuario» de cada tarjeta. Manda sobre el de los HTML de entrada.
USUARIO = {
    'taller': 'Recepción, Jefe de Taller, Mecánico, Cliente (Chatbot en web)',
    'asesorias': 'Asesores fiscales, Gestores, cualquier oficina y sus clientes, agentes, proveedores, acreedores',
    'clinicas': 'Recepción, Dentistas, Higienistas, Médicos, Sicólogos, Dueños',
    'obra': 'Jefes de obra, Aparejadores, Encargados, Dueños y Clientes',
}

# Tarjetas nuevas (las 4 originales se leen del HTML).
NUEVAS = [
    {
        'id': 'obra',
        'titulo': 'Obra Clara',
        'usuario': USUARIO['obra'],
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
    '.acciones .access{margin-top:0;align-self:auto}\n'
    '.access-app{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;'
    'padding:10px 22px;border-radius:12px;border:2px solid var(--c);background:transparent;color:var(--ink);'
    'font:inherit;font-weight:700;text-decoration:none}\n'
    '.access svg,.access-app svg{width:18px;height:18px;flex:none}\n'
    '.access-app:hover{background:var(--tint)}\n'
    '@media (max-width:820px){.acciones{flex-direction:column}.acciones .access,.access-app{align-self:stretch}}\n'
)


def acciones_movil(tid):
    """Botones de una tarjeta movil, en este orden: «Información» (si hay texto), «Ver demo»
    (o la etiqueta propia de la tarjeta) y, si hay app publicada, «Ver app»."""
    botones = []
    if tid in INFO:
        botones.append(f'<button class="access-info" type="button" data-info="{tid}" aria-pressed="false">'
                       f'{ICONO_PRESENTACION} Información</button>')
    botones.append(f'<button class="access" type="button" data-app="{tid}" disabled>'
                   f'{ICONO_PELI} {ETIQUETA_DEMO.get(tid, "Ver demo")}</button>')
    if tid in APP_URL:
        botones.append(f'<a class="access-app" href="{APP_URL[tid]}" target="_blank" rel="noopener">'
                       f'{ICONO_APP} Ver app</a>')
    if len(botones) == 1:
        return f'        {botones[0]}\n'
    return '        <div class="acciones">\n' + ''.join(f'          {b}\n' for b in botones) + '        </div>\n'


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


ICONO_PELI = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
              '<rect x="2.5" y="3" width="19" height="18" rx="2.5"/>'
              '<path d="M7 3v18M17 3v18M2.5 8h4.5M2.5 12h4.5M2.5 16h4.5M17 8h4.5M17 12h4.5M17 16h4.5"/></svg>')

# Cambios del script de la pagina movil: sin linea de estado; «Ver demo» lleva los minutos.
JS_CAMBIOS = [
    ('const fmt = seg => Math.floor(seg/60) + " min " + String(Math.round(seg%60)).padStart(2,"0") + " s";\n',
     "const ICONO_PELI = '" + ICONO_PELI + "';\n"
     'const mins = seg => Math.max(1, Math.round(seg/60)) + " min";\n'),
    ('  const estado = cell.querySelector(".estado"), txt = estado.querySelector(".txt"), '
     'aviso = cell.querySelector(".aviso");\n',
     '  const aviso = cell.querySelector(".aviso");\n'),
    ('      estado.dataset.estado = "lista";\n'
     '      txt.textContent = "Vídeo listo · " + fmt(r.dur);\n'
     '      btn.disabled = false; btn.textContent = "▶ Ver demo";\n',
     '      btn.disabled = false; btn.innerHTML = ICONO_PELI + " Ver demo · " + mins(r.dur);\n'),
    ('      estado.dataset.estado = "proximamente";\n'
     '      txt.textContent = "Sin vídeo todavía";\n',
     ''),
    ('      estado.dataset.estado = "falta";\n'
     '      txt.textContent = "Vídeo no encontrado";\n',
     ''),
]


# Etiqueta propia del boton de demo (por defecto «Ver demo»; sin video, «Demo próximamente»).
ETIQUETA_DEMO = {'circulos': 'Demo en móvil'}

ICONO_PRESENTACION = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
                      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                      '<path d="M2 3h20"/><path d="M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"/>'
                      '<path d="m7 21 5-5 5 5"/></svg>')

# Iconos (24x24, trazo) de las slides de texto.
ICONOS_INFO = {
    'clientes': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
                '<path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    'micro': '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>'
             '<path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"/>',
    'calendario': '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    'ladron': '<path d="M3 10h18M6.5 10 8 4.5h8L17.5 10"/><circle cx="9" cy="14" r="2"/>'
              '<circle cx="15" cy="14" r="2"/><path d="M11 14h2M6.5 17.5c1.2 2.4 3 3.5 5.5 3.5s4.3-1.1 5.5-3.5"/>',
}

# Slides de texto de cada tarjeta (texto, icono opcional): van entre las fotos del carrusel.
INFO = {
    'taller': [
        ('El cliente solicita sus citas, consulta precios, revisa el estado', 'clientes'),
        ('Los mecánicos modifican el parte en modo «voz»', 'micro'),
        ('Identificación visual de piezas', None),
        ('QR Inteligente', 'ladron'),
    ],
    'circulos': [
        ('Los voluntarios se ofrecen para tareas según su disponibilidad', None),
        ('La aplicación puede asignar automáticamente', None),
        ('Si uno no puede, va al siguiente de la lista', None),
        ('Tareas por categorías para score de asignación', None),
    ],
    'asesorias': [
        ('Repositorio documental', None),
        ('Identificación visual de tickets', None),
        ('Las consultas por IA extienden la funcionalidad del aplicativo (texto o voz)', None),
    ],
    'clinicas': [
        ('El cliente solicita sus citas, consulta precios, revisa el estado', 'calendario'),
        ('Lista de espera (para un médico en concreto, o si sale fecha anterior a la solicitada)', None),
        ('Informe médico y procedimientos en modo voz / texto', None),
        ('Confidencialidad de datos', None),
        ('Responsabilidad facultativa con opción a firma delegada', None),
    ],
    'obra': [
        ('Control de presupuesto', None),
        ('Trabajos extra', None),
        ('Materiales extra', None),
        ('Asistente de Fotografías antes/después', None),
        ('El encargado y el dueño están al tanto preciso de la evolución', None),
    ],
}

CSS_INFO = (
    '.access-info{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;'
    'padding:10px 22px;border-radius:12px;border:2px solid transparent;background:var(--tint);color:var(--ink);'
    'font:inherit;font-weight:700}\n'
    '.access-info svg{width:18px;height:18px;flex:none}\n'
    '.access-info:hover{filter:brightness(.96)}\n'
    '.access-info[aria-pressed="true"]{background:var(--c);color:#fff}\n'
    '[data-theme="dark"] .access-info[aria-pressed="true"]{color:#12151b}\n'
    '/* Slides de texto del carrusel: fondo del color de la tarjeta, letras grandes */\n'
    '.slide-texto{display:flex;flex-direction:column;justify-content:center;gap:clamp(8px,3cqw,18px);'
    'padding:clamp(18px,5cqw,36px) clamp(58px,15cqw,92px);background:var(--c);color:#fff;overflow:hidden}\n'
    '[data-theme="dark"] .slide-texto{color:#12151b}\n'
    '.slide-texto svg{width:clamp(34px,10cqw,56px);height:clamp(34px,10cqw,56px);flex:none}\n'
    '.slide-texto p{margin:0;font-size:1.35rem;font-weight:800;line-height:1.2;letter-spacing:-.01em;'
    'overflow-wrap:anywhere;hyphens:auto}\n'
    '@supports (font-size:1cqw){.slide-texto p{font-size:clamp(1.2rem,6.8cqw,2.2rem)}}\n'
)

AUTO_JS = r"""// ---- Información: las slides pasan solas hasta mover la página o pulsar otro botón ----
const PAUSA_FOTO = 3000, PAUSA_TEXTO = 5000;
let auto = null;
function pararAuto(){
  if(!auto) return;
  clearTimeout(auto.t);
  auto.btn.setAttribute("aria-pressed","false");
  auto = null;
}
function iniciarAuto(btn, car){
  const ctl = car._ctl;
  if(!ctl) return;
  pararAuto();
  const n = ctl.slides.length;
  auto = { btn, t:0, desde:Date.now() };
  btn.setAttribute("aria-pressed","true");
  const paso = k=>{
    ctl.go(k);
    auto.t = setTimeout(()=>paso((k+1)%n), ctl.slides[k].classList.contains("slide-texto") ? PAUSA_TEXTO : PAUSA_FOTO);
  };
  paso(Math.max(0, ctl.slides.findIndex(s=>s.classList.contains("slide-texto"))));
}
document.querySelectorAll("[data-info]").forEach(btn=>{
  const car = btn.closest(".cell").querySelector(".carousel");
  btn.addEventListener("click", ()=>{ if(auto && auto.btn === btn) pararAuto(); else iniciarAuto(btn, car); });
});
// Pulsar cualquier otro botón, mover la página o salir de la pestaña detiene el pase.
document.addEventListener("click", e=>{
  const b = e.target.closest("button, a");
  if(auto && b && b !== auto.btn) pararAuto();
}, true);
["scroll","wheel","touchmove"].forEach(ev=>window.addEventListener(ev, ()=>{
  if(auto && Date.now() - auto.desde > 600) pararAuto();
}, {passive:true}));
document.addEventListener("visibilitychange", ()=>{ if(document.hidden) pararAuto(); });
"""

JS_CAMBIOS += [
    # «Demo en móvil» (etiqueta propia) en la configuracion y en los estados del boton.
    ('  circulos:  { file:"circulos.mp4",  proximamente:true },\n',
     '  circulos:  { file:"circulos.mp4",  proximamente:true, etiqueta:"Demo en móvil" },\n'),
    ('btn.innerHTML = ICONO_PELI + " Ver demo · " + mins(r.dur);',
     'btn.innerHTML = ICONO_PELI + " " + (cfg.etiqueta || "Ver demo") + " · " + mins(r.dur);'),
    ('btn.disabled = true; btn.textContent = "Demo próximamente";',
     'btn.disabled = true; btn.textContent = cfg.etiqueta || "Demo próximamente";'),
    # Carrusel: cada uno expone su control (go + slides) para el pase automatico.
    ('const track=c.querySelector(".track"), n=c.querySelectorAll(".slide").length, label=c.dataset.label;',
     'const track=c.querySelector(".track"), slides=[...c.querySelectorAll(".slide")], n=slides.length, '
     'label=c.dataset.label;'),
    ('  c.append(prev,next,dots); go(0);\n});\n</script>',
     '  c.append(prev,next,dots); go(0);\n  c._ctl = { go, slides };\n});\n' + AUTO_JS + '</script>'),
]


def intercalar(fotos, textos):
    """Fotos y slides de texto: la primera foto, la mitad de los textos, la segunda foto y el resto."""
    if not textos:
        return fotos
    if len(fotos) < 2:
        return fotos + textos
    k = (len(textos) + 1) // 2
    return [fotos[0]] + textos[:k] + [fotos[1]] + textos[k:] + fotos[2:]


def slide_texto(contenido, icono):
    svg = ''
    if icono:
        svg = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
               f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONOS_INFO[icono]}</svg>')
    return f'          <div class="slide slide-texto">{svg}<p>{htmlmod.escape(contenido)}</p></div>'


def anadir_info(texto):
    """Mete las slides de texto entre las fotos de cada carrusel y deja los botones de la
    tarjeta (Informacion, Ver demo, Ver app) como los define acciones_movil (idempotente)."""
    for tid, items in INFO.items():
        pista = re.compile(rf'(<article class="cell {tid}">.*?<div class="track">\n)(.*?)(\n        </div>\n      </div>)', re.S)
        m = pista.search(texto)
        if not m:
            sys.exit(f'No encuentro el carrusel de {tid} en el HTML movil')
        lineas = m.group(2).split('\n')
        fotos = [l for l in lineas if 'slide-texto' not in l]
        textos = [slide_texto(t, i) for t, i in items]
        nuevo = '\n'.join(intercalar(fotos, textos))
        texto = texto[:m.start(2)] + nuevo + texto[m.end(2):]
        botones = re.compile(
            rf'(<article class="cell {tid}">.*?<p class="user">[^\n]*</p>\n)'
            r'(?:        <div class="acciones">\n.*?        </div>\n|        <button class="access"[^\n]*</button>\n)',
            re.S)
        m = botones.search(texto)
        if not m:
            sys.exit(f'No encuentro los botones de {tid} en el HTML movil')
        texto = texto[:m.start()] + m.group(1) + acciones_movil(tid) + texto[m.end():]
    return texto


def anadir_css_info(texto):
    if '.access-info{' not in texto:
        texto = sustituir(texto, '.access-app:hover{background:var(--tint)}\n',
                          '.access-app:hover{background:var(--tint)}\n' + CSS_INFO, 'estilo de «Información» (movil)')
    if 'container-type' not in texto:
        texto = sustituir(texto, '.carousel{position:relative;aspect-ratio:4/3;overflow:hidden;background:var(--tint)}',
                          '.carousel{position:relative;aspect-ratio:4/3;overflow:hidden;background:var(--tint);'
                          'container-type:inline-size}', 'carrusel (movil)')
    texto = texto.replace('6.2cqw,2.2rem', '6.8cqw,2.2rem')   # letras algo mas grandes (HTML ya generado)
    return texto.replace('.dot[aria-current="true"]{background:var(--c)}',
                         '.dot[aria-current="true"]{background:#fff}')


CSS_ACCESO_DEMO = (
    '.acceso-demo code{font:600 .92em ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;'
    'background:var(--tint);color:var(--ink);padding:1px 6px;border-radius:6px;white-space:nowrap}'
)


def completar_ver_app(texto):
    """Pone «Ver app» junto a «Ver demo» en las tarjetas que ya tienen sus botones y aun no ese
    (idempotente). Complementa a `anadir_ver_app`, que solo sirve con el HTML recien generado."""
    for tid, url in APP_URL.items():
        m = re.search(rf'<article class="cell {tid}">.*?</article>', texto, re.S)
        if not m or 'class="access-app"' in m.group(0) or '<div class="acciones">' not in m.group(0):
            continue
        boton = re.search(rf'          <button class="access" type="button" data-app="{tid}" disabled>.*?</button>\n',
                          m.group(0), re.S)
        if not boton:
            continue
        enlace = (f'          <a class="access-app" href="{url}" target="_blank" rel="noopener">'
                  f'{ICONO_APP} Ver app</a>\n')
        texto = texto.replace(m.group(0), m.group(0).replace(boton.group(0), boton.group(0) + enlace, 1), 1)
    return texto


def anadir_acceso_demo(texto):
    """«Acceso de prueba» bajo el «Usuario» de las tarjetas de ACCESO_DEMO (idempotente: lo rehace)."""
    for tid, acceso in ACCESO_DEMO.items():
        m = re.search(rf'<article class="cell {tid}">.*?</article>', texto, re.S)
        if not m:
            continue
        cuentas = ' · '.join(f'{htmlmod.escape(rol.lower())} <code>{htmlmod.escape(correo)}</code>'
                             for rol, correo in acceso['lineas'])
        parrafo = (f'        <p class="user acceso-demo"><strong>Acceso de prueba:</strong> {cuentas}. '
                   f'Contraseña de ambas: <code>{htmlmod.escape(acceso["clave"])}</code></p>\n')
        cuerpo = re.sub(r'        <p class="user acceso-demo">.*?</p>\n', '', m.group(0), flags=re.S)
        usuario = re.search(r'        <p class="user"><strong>Usuario:</strong>.*?</p>\n', cuerpo, re.S)
        if not usuario:
            continue
        cuerpo = cuerpo.replace(usuario.group(0), usuario.group(0) + parrafo, 1)
        texto = texto.replace(m.group(0), cuerpo, 1)
    viejo = '.user{margin:0;color:var(--muted)}'
    texto = re.sub(r'\n\.acceso-demo code\{[^}]*\}', '', texto)   # se rehace, para que un cambio de estilo llegue
    if ACCESO_DEMO and viejo in texto:
        texto = texto.replace(viejo, viejo + '\n' + CSS_ACCESO_DEMO, 1)
    return texto


def retocar_movil(texto):
    """Ajustes de la pagina movil (idempotente): sin linea de estado del video, «Ver demo» con
    icono de pelicula y minutos, URL de cada app, textos de «Usuario» y acceso de prueba."""
    texto = completar_ver_app(anadir_css_info(anadir_info(texto)))
    # Sin linea de estado (marcado y CSS).
    texto = re.sub(r'        <p class="estado"[^\n]*</p>\n', '', texto)
    texto = re.sub(r'^(?:\.estado|\.punto|\[data-theme="dark"\] \.estado)[^\n]*\n', '', texto, flags=re.M)
    texto = texto.replace('/* Estado del vídeo de cada demo y aviso */', '/* Aviso de vídeo ausente */')
    if '.access svg,' not in texto:
        texto = texto.replace('.access-app svg{', '.access svg,.access-app svg{')
    for viejo, nuevo in JS_CAMBIOS:
        texto = texto.replace(viejo, nuevo)
    # «Ver demo» con icono de pelicula.
    texto = texto.replace('>▶ Ver demo</button>', f'>{ICONO_PELI} Ver demo</button>')
    # URL de cada app y textos de «Usuario».
    for tid, url in APP_URL.items():
        texto = re.sub(rf'(<article class="cell {tid}">.*?<a class="access-app" href=")[^"]*(")',
                       lambda m, u=url: m.group(1) + u + m.group(2), texto, count=1, flags=re.S)
    for tid, usuario in USUARIO.items():
        texto = re.sub(rf'(<article class="cell {tid}">.*?<p class="user"><strong>Usuario:</strong> )(.*?)(</p>)',
                       lambda m, u=usuario: m.group(1) + htmlmod.escape(u) + m.group(3),
                       texto, count=1, flags=re.S)
    return anadir_acceso_demo(texto)


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
    return retocar_movil(anadir_ver_app(texto))


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


def pelicula(c, x, y, ancho, color):
    """Icono de pelicula (fotograma con perforaciones), como el de la pagina movil."""
    alto = ancho * 0.95
    s = ancho * 0.26
    c.saveState()
    c.setStrokeColor(color)
    c.setLineWidth(1.8)
    c.setLineCap(1)
    c.roundRect(x, y, ancho, alto, 2.5, stroke=1, fill=0)
    p = c.beginPath()
    for xx in (x + s, x + ancho - s):
        p.moveTo(xx, y)
        p.lineTo(xx, y + alto)
    for k in (0.25, 0.5, 0.75):
        p.moveTo(x, y + alto * k)
        p.lineTo(x + s, y + alto * k)
        p.moveTo(x + ancho - s, y + alto * k)
        p.lineTo(x + ancho, y + alto * k)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()


def minutos_video(ruta):
    """Minutos (redondeados, como la pagina movil) de un video; None si no se pueden medir."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'csv=p=0', str(ruta)], capture_output=True, text=True, timeout=60)
        return max(1, int(float(r.stdout.strip()) / 60 + 0.5))
    except Exception:
        return None


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
            c.drawString(M + 26, base + 15, ETIQUETA_DEMO.get(t['id'], 'Demo próximamente'))
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


def pdf_tarjeta(c, R, B, t, n, total, video_ok, incrustado=False, minutos=None):
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
    acceso = ACCESO_DEMO.get(t['id'])
    iw = 340 if len(imgs) > 1 else 440
    if acceso:
        iw = 290   # deja sitio al bloque «Acceso de prueba» sin pisar los botones
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

    # Acceso de prueba (cuentas y contrasena de la demo publicada).
    if acceso:
        y -= 4
        c.setFillColor(INK)
        c.setFont(B, 13.5)
        c.drawString(M, y, 'Acceso de prueba:')
        sangria = M + 8
        filas = [(f'{rol}:', correo) for rol, correo in acceso['lineas']] + [('Contraseña:', acceso['clave'])]
        columna = sangria + max(pdfmetrics.stringWidth(e, R, 12.5) for e, _ in filas) + 10
        for etiqueta, valor in filas:
            y -= 17
            c.setFillColor(MUTED)
            c.setFont(R, 12.5)
            c.drawString(sangria, y, etiqueta)
            c.setFillColor(INK)
            c.setFont(B, 12.5)
            c.drawString(columna, y, valor)

    # Boton de video (o aviso de que aun no hay).
    bh = 52
    by = 74
    bx, bw = caja_demo(t['id'])
    if video_ok:
        c.setFillColor(color)
        c.roundRect(bx, by, bw, bh, 12, stroke=0, fill=1)
        etiqueta = ETIQUETA_DEMO.get(t['id'], 'Ver demo') + (f' · {minutos} min' if minutos else '')
        c.setFont(B, 16)
        ancho = pdfmetrics.stringWidth(etiqueta, B, 16)
        x0 = bx + (bw - (ancho + 30)) / 2
        pelicula(c, x0, by + bh / 2 - 8.5, 18, white)
        c.setFillColor(white)
        c.drawString(x0 + 30, by + bh / 2 - 5.5, etiqueta)
        if not incrustado:
            # Con el video dentro del PDF no hay enlace a archivo (apuntaria a un archivo
            # que no existe junto al PDF y abriria el navegador con un error).
            c.linkURL(VIDEO[t['id']], (bx, by, bx + bw, by + bh), relative=0, thickness=0)
    else:
        c.setFillColor(HexColor('#eceef2'))
        c.roundRect(bx, by, bw, bh, 12, stroke=0, fill=1)
        c.setFillColor(MUTED)
        c.setFont(B, 16)
        c.drawCentredString(bx + bw / 2, by + bh / 2 - 5.5,
                            ETIQUETA_DEMO.get(t['id'], 'Demo próximamente'))
    if t['id'] in APP_URL:
        pdf_boton_app(c, B, t['id'], color, by, bh)
    c.setFillColor(MUTED)
    c.setFont(R, 10)
    c.drawRightString(W - M, 48, f'{n} / {total}')
    c.showPage()


def escribir_pdf(salida: Path, tarjetas, carpeta_videos: Path, incrustado=False):
    R, B = fuentes()
    salida.parent.mkdir(parents=True, exist_ok=True)

    def hay_video(tid):
        return (carpeta_videos / VIDEO[tid]).exists()

    def minutos(tid):
        return minutos_video(carpeta_videos / VIDEO[tid]) if hay_video(tid) else None

    c = canvas.Canvas(str(salida), pagesize=A4)
    c.setTitle('Portafolio · Enfoque IA')
    c.setAuthor('Enfoque IA')
    c.setSubject('Aplicaciones de IA por sector: fichas y demos en vídeo')
    pdf_portada(c, R, B, tarjetas, hay_video, incrustado)
    for i, t in enumerate(tarjetas, start=2):
        pdf_tarjeta(c, R, B, t, i, len(tarjetas) + 1, hay_video(t['id']), incrustado,
                    minutos(t['id']))
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
    for t in todas:
        t['usuario'] = USUARIO.get(t['id'], t['usuario'])

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
