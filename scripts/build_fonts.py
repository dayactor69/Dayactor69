#!/usr/bin/env python3
"""
Scarica JetBrains Mono e la riduce ai soli glifi usati, una volta sola.

Gira in locale, non in CI: richiede `pip install fonttools brotli`.
Produce assets/fonts/jbm-<peso>.b64, che generate.py incorpora negli SVG.

Perché incorporare: gli SVG vengono caricati da GitHub dentro un tag <img>, e
un documento-immagine non può scaricare sottorisorse. Un URL di font non
verrebbe mai richiesto; un data URI sì.

Licenza: JetBrains Mono è SIL Open Font License 1.1 — si può ridistribuire,
anche in un repository pubblico, tenendo il file di licenza accanto.
"""
import base64
import io
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

QUI = Path(__file__).resolve().parent
FONTS = QUI.parent / 'assets' / 'fonts'

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/141.0 Safari/537.36'
CSS = ('https://fonts.googleapis.com/css2'
       '?family=JetBrains+Mono:wght@400;600;800&display=swap')

# ASCII stampabile + i pochi segni tipografici che uso davvero.
# Barre, celle e cursori sono <rect>, non caratteri: niente glifi a blocchi.
UNICODES = 'U+0020-007E,U+00B7,U+2013,U+2014,U+2192,U+25CF'


def scarica(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def blocchi_latin(css: str) -> dict[int, str]:
    """Dal CSS di Google Fonts tiene solo i sottoinsiemi `latin`, per peso."""
    fuori = {}
    for pezzo in css.split('/*')[1:]:
        if not pezzo.startswith(' latin */'):
            continue
        peso = re.search(r'font-weight:\s*(\d+)', pezzo)
        url = re.search(r'url\((https:[^)]+)\)', pezzo)
        if peso and url:
            fuori[int(peso.group(1))] = url.group(1)
    return fuori


def main() -> int:
    FONTS.mkdir(parents=True, exist_ok=True)
    css = scarica(CSS).decode('utf-8')
    sorgenti = blocchi_latin(css)
    if not sorgenti:
        print('Nessun sottoinsieme latin trovato nel CSS.', file=sys.stderr)
        return 1

    totale = 0
    for peso in sorted(sorgenti):
        grezzo = FONTS / f'_jbm-{peso}.woff2'
        grezzo.write_bytes(scarica(sorgenti[peso]))

        ridotto = FONTS / f'_jbm-{peso}-sub.woff2'
        subprocess.run(
            [sys.executable, '-m', 'fontTools.subset', str(grezzo),
             f'--unicodes={UNICODES}', '--flavor=woff2',
             "--layout-features=''", '--no-hinting',
             f'--output-file={ridotto}'],
            check=True, capture_output=True)

        b64 = base64.b64encode(ridotto.read_bytes()).decode('ascii')
        (FONTS / f'jbm-{peso}.b64').write_text(b64)
        totale += len(b64)
        print(f'  peso {peso}: {ridotto.stat().st_size / 1024:5.1f} KB '
              f'→ {len(b64) / 1024:5.1f} KB in base64')

        grezzo.unlink()
        ridotto.unlink()

    print(f'\nTotale incorporato per SVG: {totale / 1024:.1f} KB')
    print('Ricorda la licenza: assets/fonts/OFL.txt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
