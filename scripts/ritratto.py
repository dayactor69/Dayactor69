#!/usr/bin/env python3
"""
Ritratto ASCII che si scrive da solo, da una fotografia.

    python3 scripts/ritratto.py foto.jpg
    python3 scripts/ritratto.py foto.jpg --colonne 90 --larghezza 460

Gira in locale, non in CI: il risultato si committa una volta e non cambia
più. Le uniche dipendenze obbligatorie sono Pillow e numpy.

    pip install pillow numpy                    # minimo
    pip install opencv-python-headless rembg    # qualità piena

Le due opzionali fanno la differenza:
  · rembg  ritaglia il soggetto e forza a bianco tutto il resto. Senza, lo
           sfondo si riempie di '@' e il volto ci annega dentro.
  · cv2    dà il contrasto locale (CLAHE) e lo sfocamento che preserva i
           bordi. Senza, si ripiega su equalizzazione globale: accettabile
           con una foto ben illuminata di lato, mediocre con luce piatta.

Sulla foto, che conta più di qualsiasi parametro:
  · luce laterale, una finestra a ~45°, il resto spento. L'ASCII disegna con
    le ombre, non con i dettagli: ha tredici livelli di grigio in tutto.
  · inquadratura stretta, dal mento a poco sopra i capelli.
  · almeno 1200px sul lato lungo. Una miniatura perde gli occhiali.
  · sfondo semplice, e niente nero su nero.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import svgkit as sk
from svgkit import TEMI, esc

# Dal pieno al vuoto. Lo spazio in testa azzera lo sfondo: senza, il bianco
# diventa un carattere e il ritratto perde il suo silenzio attorno.
RAMPA = ' .`:-=+*csS#%@'

# I caratteri monospazio sono circa il doppio più alti che larghi.
PROPORZIONE = 0.48


def prepara(percorso: Path, colonne: int, gamma: float) -> np.ndarray:
    img = Image.open(percorso)
    img = ImageOps.exif_transpose(img).convert('RGB')

    try:
        from rembg import remove  # type: ignore
        ritagliata = remove(img)
        fondo = Image.new('RGB', ritagliata.size, (255, 255, 255))
        fondo.paste(ritagliata, mask=ritagliata.split()[3])
        img = fondo
        print('  soggetto ritagliato (rembg)')
    except ImportError:
        print('  rembg assente: lo sfondo resterà nel disegno', file=sys.stderr)

    g = np.asarray(img.convert('L'))

    try:
        import cv2  # type: ignore
        g = cv2.bilateralFilter(g, 9, 60, 60)
        g = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(g)
        print('  contrasto locale (CLAHE) applicato')
    except ImportError:
        print('  cv2 assente: equalizzazione globale', file=sys.stderr)
        g = np.asarray(ImageOps.equalize(Image.fromarray(g)))

    # La correzione che decide tutto. Senza, il volto esce slavato e senza
    # tratti: la curva schiaccia i toni chiari e lascia respirare le ombre,
    # ed è ciò che fa sopravvivere occhiali, sopracciglia e labbra.
    g = (255.0 * (g / 255.0) ** gamma).astype(np.uint8)

    alt, larg = g.shape
    righe = max(1, int(colonne * (alt / larg) * PROPORZIONE))
    ridotta = Image.fromarray(g).resize((colonne, righe), Image.LANCZOS)
    return np.asarray(ridotta)


def in_caratteri(g: np.ndarray) -> list[str]:
    # 255 (bianco) → indice 0, cioè lo spazio.
    indici = ((255 - g.astype(np.int32)) * (len(RAMPA) - 1)) // 255
    return [''.join(RAMPA[i] for i in riga) for riga in indici]


def disegna(righe: list[str], tema: dict, larghezza_px: int, ritardo: float) -> str:
    colonne = max(len(r) for r in righe)
    dim = larghezza_px / (colonne * sk.PASSO)
    interlinea = dim * 1.06
    alt = int(len(righe) * interlinea + dim)

    out = [sk.apri(larghezza_px, alt, (400,), 'Ritratto in caratteri')]
    # Un solo colore. Colorare carattere per carattere è ciò che fa sembrare
    # questi ritratti un disturbo di segnale invece di un disegno.
    colore = tema['ink']

    for i, riga in enumerate(righe):
        y = dim + i * interlinea
        larg = sk.larghezza(riga, dim)
        out.append(
            f'<clipPath id="r{i}"><rect x="0" y="{y - dim:.2f}" width="0" '
            f'height="{interlinea + 2:.2f}">'
            f'<animate attributeName="width" from="0" to="{larg:.2f}" '
            f'begin="{i * ritardo:.2f}s" dur="0.5s" fill="freeze"/></rect></clipPath>'
            f'<g clip-path="url(#r{i})"><text x="0" y="{y:.2f}" font-size="{dim:.3f}" '
            f'fill="{colore}" xml:space="preserve">{esc(riga)}</text></g>'
            f'<rect x="0" y="{y - dim * 0.85:.2f}" width="{dim * sk.PASSO:.2f}" '
            f'height="{dim:.2f}" fill="{tema["accent"]}" opacity="0">'
            f'<animate attributeName="x" from="0" to="{larg:.2f}" '
            f'begin="{i * ritardo:.2f}s" dur="0.5s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{i * ritardo:.2f}s"/>'
            f'<set attributeName="opacity" to="0" begin="{i * ritardo + 0.5:.2f}s"/>'
            f'</rect>')
    out.append(sk.chiudi())
    return ''.join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('foto', type=Path)
    ap.add_argument('--colonne', type=int, default=90,
                    help='sotto le 88 il volto impasta, sopra le 100 domina la pagina')
    ap.add_argument('--larghezza', type=int, default=460, help='larghezza resa, in px')
    ap.add_argument('--gamma', type=float, default=1.7,
                    help='curva di scurimento; alzala se il volto esce slavato')
    ap.add_argument('--ritardo', type=float, default=0.09,
                    help='sfasamento fra una riga e la successiva, in secondi')
    ap.add_argument('--out', type=Path, default=Path('img'))
    ap.add_argument('--txt', action='store_true', help='stampa anche il testo a terminale')
    args = ap.parse_args()

    if not args.foto.exists():
        print(f'Foto non trovata: {args.foto}', file=sys.stderr)
        return 2

    print(f'{args.foto} → {args.colonne} colonne, gamma {args.gamma}')
    griglia = prepara(args.foto, args.colonne, args.gamma)
    righe = in_caratteri(griglia)

    pieni = sum(1 for r in righe for c in r if c != ' ')
    quota = pieni / max(1, sum(len(r) for r in righe))
    print(f'  {len(righe)} righe · {quota * 100:.0f}% di caratteri disegnati')
    if quota > 0.85:
        print('  ⚠ quasi tutto pieno: manca il ritaglio dello sfondo, o la foto '
              'è troppo scura. Prova ad abbassare --gamma.', file=sys.stderr)
    elif quota < 0.15:
        print('  ⚠ quasi tutto vuoto: la foto è troppo chiara o troppo piatta. '
              'Prova ad alzare --gamma.', file=sys.stderr)

    if args.txt:
        print('\n'.join(righe))

    args.out.mkdir(parents=True, exist_ok=True)
    for nome, tema in TEMI.items():
        f = args.out / f'ritratto-{nome}.svg'
        f.write_text(disegna(righe, tema, args.larghezza, args.ritardo), encoding='utf-8')
        print(f'  {f}  ({f.stat().st_size / 1024:.0f} KB)')

    durata = (len(righe) - 1) * args.ritardo + 0.5
    print(f'\nLa scrittura dura {durata:.1f}s. Per metterlo nel README:\n')
    print(f'''<picture>
  <source media="(prefers-color-scheme: dark)" srcset="{args.out}/ritratto-dark.svg">
  <img alt="Ritratto in caratteri" src="{args.out}/ritratto-light.svg" width="{args.larghezza}">
</picture>''')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
