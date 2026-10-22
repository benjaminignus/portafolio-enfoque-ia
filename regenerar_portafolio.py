"""Regenera la pagina movil (index.html) y los dos PDF del portafolio a partir de portafolio-movil.html.

No toca el HTML de escritorio ni necesita las fotos: las tarjetas se leen de la propia pagina movil.
Uso: python regenerar_portafolio.py [--sin-incrustado]
"""
import sys
from pathlib import Path

REPO = Path(r'D:\claude\portafolio\portafolio')
sys.path.insert(0, str(REPO))
import generar_portafolio as g  # noqa: E402

movil = REPO / 'portafolio-movil.html'
crudo = movil.read_bytes()
bom = crudo.startswith(b'\xef\xbb\xbf')
texto = crudo.decode('utf-8-sig')
crlf = '\r\n' in texto
texto = g.retocar_movil(texto.replace('\r\n', '\n'))

salida = texto.replace('\n', '\r\n') if crlf else texto
movil.write_bytes((b'\xef\xbb\xbf' if bom else b'') + salida.encode('utf-8'))
(REPO / 'index.html').write_bytes(texto.encode('utf-8'))
print('pagina movil e index.html actualizados')

tarjetas = g.leer_tarjetas_originales(texto)
for t in tarjetas:
    t['usuario'] = g.USUARIO.get(t['id'], t['usuario'])
print('tarjetas:', [t['id'] for t in tarjetas])

g.escribir_pdf(REPO / 'Portafolio ENFOQUE IA.pdf', tarjetas, REPO)
print('PDF normal escrito')
if '--sin-incrustado' not in sys.argv:
    g.escribir_pdf(REPO / 'Portafolio ENFOQUE IA - videos incrustados.pdf', tarjetas, REPO, incrustado=True)
    print('PDF incrustado escrito')
