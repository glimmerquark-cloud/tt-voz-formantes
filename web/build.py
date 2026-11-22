"""Arma la pagina unica: inserta voz.js y (si existe) el render del layout."""
import base64, sys
from pathlib import Path
here = Path(__file__).parent
html = (here / "page_template.html").read_text(encoding="utf-8")
html = html.replace("/*VOZJS*/", (here / "voz.js").read_text(encoding="utf-8"))
img = here / "layout.png"
if img.exists():
    b64 = base64.b64encode(img.read_bytes()).decode()
    lay = (f'<img src="data:image/png;base64,{b64}" alt="Layout GDS del tile 1x1 en GF180" '
           'style="width:100%;border-radius:6px;background:#000">'
           '<p class="note">Render del GDS final (346.64 × 160.72 µm) del flujo de Tiny Tapeout: 211 flip-flops, 64.6 % de uso en placement, sin violaciones de setup ni hold a 10 MHz.</p>')
else:
    lay = ('<p class="note">El render del GDS se agrega aquí cuando termina el flujo de Tiny Tapeout. '
           'Mientras tanto, el visor 3D estará en <a href="https://glimmerquark-cloud.github.io/tt-voz-formantes/" '
           'target="_blank" rel="noopener">glimmerquark-cloud.github.io/tt-voz-formantes</a>.</p>')
html = html.replace("<!--LAYOUT-->", lay)
out = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "chip_que_habla.html"
out.write_text(html, encoding="utf-8")
print(out, len(html))
