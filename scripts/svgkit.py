"""
Mattoni SVG condivisi. Solo libreria standard.

Due scelte che governano tutto il resto:

1. **Sfondo trasparente.** Gli SVG non disegnano un rettangolo di fondo: si
   appoggiano al colore della pagina di GitHub. Un pannello con il proprio
   fondo si vede subito che è stato incollato lì; questi sembrano parte della
   pagina. Il prezzo è che servono due varianti di colore, chiara e scura,
   scelte dal browser con <picture> — che ne scarica una sola.

2. **Font incorporato come data URI.** Questi file arrivano dentro un <img>, e
   un documento-immagine non può scaricare sottorisorse: un URL di font non
   verrebbe mai richiesto. Ogni file porta quindi la sua copia dei pesi che usa.

Il passo dei caratteri di JetBrains Mono è 600/1000 di em, cioè esattamente
0.6: le posizioni orizzontali si calcolano, non si misurano.
"""
from __future__ import annotations

from pathlib import Path

PASSO = 0.6  # avanzamento di un carattere, in em

FONTS = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'

TEMI = {
    'dark': {
        'ink':     '#e6edf3',
        'muted':   '#8b949e',
        'faint':   '#6e7681',
        'rule':    '#30363d',
        'accent':  '#e3a008',
        'ok':      '#3fb950',
        'surface': '#161b22',
        'grid0':   '#21262d',
    },
    'light': {
        'ink':     '#1f2328',
        'muted':   '#59636e',
        'faint':   '#818b98',
        'rule':    '#d1d9e0',
        'accent':  '#9a6700',
        'ok':      '#1a7f37',
        'surface': '#f6f8fa',
        'grid0':   '#eaeef2',
    },
}


def larghezza(testo: str, dim: float) -> float:
    """Larghezza in px di una stringa monospazio."""
    return len(testo) * PASSO * dim


def taglia(s: str, dim: float, max_px: float) -> str:
    """Accorcia una stringa perché stia in `max_px`. Serve come rete: le note
    sono generate dai dati e una data lunga non deve invadere la colonna
    accanto."""
    massimo = int(max_px / (PASSO * dim))
    return s if len(s) <= massimo else s[:max(0, massimo - 1)].rstrip() + '.'


def esc(s: object) -> str:
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


_cache: dict[int, str] = {}


def _font(peso: int) -> str:
    if peso not in _cache:
        _cache[peso] = (FONTS / f'jbm-{peso}.b64').read_text().strip()
    return _cache[peso]


def apri(larg: int, alt: int, pesi: tuple[int, ...], titolo: str) -> str:
    """Intestazione del file: viewBox, font incorporati, stili di base."""
    facce = '\n'.join(
        "@font-face{font-family:'JBM';font-style:normal;font-weight:%d;"
        "src:url(data:font/woff2;base64,%s) format('woff2');}" % (p, _font(p))
        for p in pesi
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{larg}" height="{alt}"
     viewBox="0 0 {larg} {alt}" role="img" aria-label="{esc(titolo)}">
<title>{esc(titolo)}</title>
<defs><style>
{facce}
text {{ font-family: 'JBM', ui-monospace, monospace; white-space: pre; }}
</style></defs>
'''


def chiudi() -> str:
    return '</svg>\n'


def testo(x: float, y: float, s: str, dim: float, colore: str,
          peso: int = 400, opacita: float = 1.0, extra: str = '') -> str:
    op = '' if opacita == 1.0 else f' opacity="{opacita}"'
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{dim}" font-weight="{peso}" '
            f'fill="{colore}"{op}{extra}>{esc(s)}</text>')


# ---------------------------------------------------------------- animazioni

def battuto(uid: str, x: float, y: float, s: str, dim: float, colore: str,
            inizio: float, durata: float, peso: int = 400,
            cursore: str | None = None) -> str:
    """
    Testo che si scrive da sinistra a destra.

    Non è un'animazione per carattere: è un rettangolo di ritaglio che si
    allarga. Costa un solo elemento animato per riga invece di uno per
    lettera, e il testo resta selezionabile e leggibile dagli screen reader.

    `fill="freeze"` su ogni animazione: la pagina si scrive una volta e si
    ferma. Niente cicli — un profilo che si riscrive all'infinito stanca.
    """
    larg = larghezza(s, dim)
    pezzi = [
        f'<clipPath id="c{uid}"><rect x="{x:.1f}" y="{y - dim:.1f}" '
        f'width="0" height="{dim * 1.45:.1f}">'
        f'<animate attributeName="width" from="0" to="{larg:.1f}" '
        f'begin="{inizio:.2f}s" dur="{durata:.2f}s" fill="freeze"/></rect></clipPath>',
        f'<g clip-path="url(#c{uid})">{testo(x, y, s, dim, colore, peso)}</g>',
    ]
    if cursore:
        # Il cursore cavalca il bordo del ritaglio e sparisce quando arriva in fondo.
        pezzi.append(
            f'<rect x="{x:.1f}" y="{y - dim * 0.82:.1f}" width="{dim * PASSO:.1f}" '
            f'height="{dim * 0.95:.1f}" fill="{cursore}" opacity="0">'
            f'<animate attributeName="x" from="{x:.1f}" to="{x + larg:.1f}" '
            f'begin="{inizio:.2f}s" dur="{durata:.2f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.9" begin="{inizio:.2f}s"/>'
            f'<set attributeName="opacity" to="0" begin="{inizio + durata:.2f}s"/>'
            f'</rect>')
    return ''.join(pezzi)


def comparso(contenuto: str, inizio: float, durata: float = 0.35,
             dy: float = 0.0) -> str:
    """Avvolge un frammento in una comparsa in dissolvenza, con leggera salita."""
    salita = ''
    if dy:
        salita = (f'<animateTransform attributeName="transform" type="translate" '
                  f'from="0 {dy}" to="0 0" begin="{inizio:.2f}s" '
                  f'dur="{durata:.2f}s" fill="freeze"/>')
    return (f'<g opacity="0">{contenuto}'
            f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{inizio:.2f}s" dur="{durata:.2f}s" fill="freeze"/>{salita}</g>')


def tracciata(d: str, colore: str, spessore: float, lunghezza: float,
              inizio: float, durata: float, extra: str = '') -> str:
    """Linea che si disegna: dasharray lunga quanto il tracciato, offset a zero."""
    return (f'<path d="{d}" fill="none" stroke="{colore}" stroke-width="{spessore}" '
            f'stroke-dasharray="{lunghezza:.1f}" stroke-dashoffset="{lunghezza:.1f}"{extra}>'
            f'<animate attributeName="stroke-dashoffset" to="0" '
            f'begin="{inizio:.2f}s" dur="{durata:.2f}s" fill="freeze"/></path>')


def barra_cresce(x: float, base: float, larg: float, alt: float, colore: str,
                 inizio: float, durata: float = 0.4, raggio: float = 1.0) -> str:
    """Colonna che sale dalla linea di base. Le colonne a zero restano vuote."""
    if alt <= 0:
        return ''
    return (f'<rect x="{x:.1f}" y="{base:.1f}" width="{larg:.2f}" height="0" '
            f'rx="{raggio}" fill="{colore}">'
            f'<animate attributeName="height" to="{alt:.1f}" begin="{inizio:.2f}s" '
            f'dur="{durata:.2f}s" fill="freeze"/>'
            f'<animate attributeName="y" to="{base - alt:.1f}" begin="{inizio:.2f}s" '
            f'dur="{durata:.2f}s" fill="freeze"/></rect>')


def pallino_vivo(cx: float, cy: float, r: float, colore: str, inizio: float) -> str:
    """
    Indicatore «in linea»: un alone che pulsa.

    È l'unica animazione che continua all'infinito, e ha una ragione — segnala
    uno stato presente, non un evento passato. Tutto il resto si congela.
    """
    return (
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
        f'begin="{inizio:.2f}s" dur="0.3s" fill="freeze"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colore}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colore}" stroke-width="1.2">'
        f'<animate attributeName="r" values="{r};{r * 3.2}" dur="2.4s" '
        f'begin="{inizio + 0.3:.2f}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="0.55;0" dur="2.4s" '
        f'begin="{inizio + 0.3:.2f}s" repeatCount="indefinite"/></circle></g>')
