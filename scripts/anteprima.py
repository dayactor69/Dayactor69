#!/usr/bin/env python3
"""
Pagina di revisione con gli SVG inlineati, per rivedere le animazioni.

    python3 scripts/anteprima.py && apri anteprima.html

Inlineare invece di usare <img> ha una ragione precisa: un SVG dentro un tag
immagine non è scriptabile, quindi non se ne può pilotare il tempo. Inlineato
sì — ed è l'unico modo di rivedere la sequenza senza ricaricare la pagina, o
di fotografarne lo stato finale con un browser headless.

Il file prodotto non va committato: pesa quanto tutti gli SVG messi insieme.
"""
from pathlib import Path

IMG = Path(__file__).resolve().parent.parent / 'img'
ORDINE = ['hero', 'h-percorso', 'path', 'h-attivita', 'stats', 'year',
          'h-linguaggi', 'langs', 'h-stack', 'stack', 'h-contatti']


def blocco(tema: str) -> str:
    pezzi = []
    for n in ORDINE:
        f = IMG / f'{n}-{tema}.svg'
        if f.exists():
            pezzi.append(f'<div class="grafica">{f.read_text(encoding="utf-8")}</div>')
    return '\n'.join(pezzi)


pagina = f'''<title>Profilo GitHub — anteprima animata</title>
<style>
:root {{
  --carta: #ffffff;
  --inchiostro: #1f2328;
  --tenue: #59636e;
  --filo: #d1d9e0;
  --accento: #9a6700;
  --gh-scuro: #0d1117;
  --gh-chiaro: #ffffff;
  --mono: ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace;
  --testo: ui-serif, Georgia, "Times New Roman", serif;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --carta:#0e1113; --inchiostro:#e7edf2; --tenue:#9aa5b0; --filo:#262d33; --accento:#e3a008; }}
}}
:root[data-theme="dark"] {{ --carta:#0e1113; --inchiostro:#e7edf2; --tenue:#9aa5b0; --filo:#262d33; --accento:#e3a008; }}
:root[data-theme="light"] {{ --carta:#ffffff; --inchiostro:#1f2328; --tenue:#59636e; --filo:#d1d9e0; --accento:#9a6700; }}

* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--carta); color: var(--inchiostro);
  font-family: var(--testo); font-size: 17px; line-height: 1.6;
}}
.guscio {{ max-width: 61rem; margin: 0 auto; padding: 3rem 1.25rem 5rem; }}

.occhiello {{
  font-family: var(--mono); font-size: .7rem; font-weight: 600;
  letter-spacing: .2em; text-transform: uppercase; color: var(--accento);
  margin: 0 0 .9rem;
}}
h1 {{
  font-family: var(--mono); font-size: clamp(1.5rem, 4vw, 2.1rem);
  letter-spacing: -.03em; line-height: 1.1; margin: 0 0 1rem; font-weight: 600;
  text-wrap: balance;
}}
.intro {{ max-width: 62ch; color: var(--tenue); margin: 0 0 2rem; }}
.intro strong {{ color: var(--inchiostro); font-weight: 600; }}

.barra {{
  display: flex; flex-wrap: wrap; gap: .6rem; align-items: center;
  padding: .9rem 0 1.6rem; border-top: 1px solid var(--filo);
}}
button {{
  font-family: var(--mono); font-size: .8rem; font-weight: 600;
  padding: .5rem .9rem; border-radius: 5px; cursor: pointer;
  border: 1px solid var(--filo); background: transparent; color: var(--inchiostro);
}}
button:hover {{ border-color: var(--accento); color: var(--accento); }}
button:focus-visible {{ outline: 2px solid var(--accento); outline-offset: 2px; }}
.nota {{ font-family: var(--mono); font-size: .72rem; color: var(--tenue); }}

.tela {{ border: 1px solid var(--filo); border-radius: 8px; overflow: hidden; margin-bottom: 2.5rem; }}
.etichetta-tela {{
  font-family: var(--mono); font-size: .68rem; letter-spacing: .13em;
  text-transform: uppercase; color: var(--tenue);
  padding: .6rem .9rem; border-bottom: 1px solid var(--filo);
}}
.pagina {{ padding: 1.75rem 1.25rem; display: grid; gap: 1.2rem; }}
.pagina.scura {{ background: var(--gh-scuro); }}
.pagina.chiara {{ background: var(--gh-chiaro); }}
.grafica svg {{ display: block; width: 100%; height: auto; }}

.chiusa {{
  border-top: 1px solid var(--filo); padding-top: 1.5rem; margin-top: 1rem;
  font-family: var(--mono); font-size: .78rem; color: var(--tenue);
  max-width: 62ch; line-height: 1.75;
}}
.chiusa code {{ color: var(--accento); }}
</style>

<div class="guscio">
  <p class="occhiello">Anteprima · dati campione</p>
  <h1>La pagina GitHub, disegnata dal suo repository</h1>
  <p class="intro">
    Queste sono le grafiche vere, animate, non uno screenshot. Ogni file si porta
    dentro il proprio carattere e la propria animazione: <strong>nessuna richiesta a
    servizi esterni</strong>. I numeri qui sotto sono inventati — il timbro
    «dati campione» sparisce alla prima esecuzione con i tuoi dati.
  </p>

  <div class="barra">
    <button id="rivedi" type="button">↻ rivedi l'animazione</button>
    <span class="nota">la sequenza dura circa 3 secondi</span>
  </div>

  <div class="tela">
    <p class="etichetta-tela">come appare su GitHub in tema scuro</p>
    <div class="pagina scura">
{blocco('dark')}
    </div>
  </div>

  <div class="tela">
    <p class="etichetta-tela">come appare su GitHub in tema chiaro</p>
    <div class="pagina chiara">
{blocco('light')}
    </div>
  </div>

  <p class="chiusa">
    Il ritratto ASCII non c'è: serve una fotografia. La pipeline è in
    <code>scripts/ritratto.py</code>, e in <code>GUIDA.md</code> c'è che foto
    serve — luce laterale a 45°, inquadratura stretta, almeno 1200px.
  </p>
</div>

<script>
// Gli SVG sono inlineati, quindi il loro tempo è pilotabile: dentro un <img>
// non lo sarebbe. Serve solo a rivedere la sequenza senza ricaricare.
document.getElementById('rivedi').addEventListener('click', () => {{
  document.querySelectorAll('.grafica svg').forEach((s) => {{
    s.setCurrentTime(0);
    s.unpauseAnimations();
  }});
}});
</script>
'''

fuori = Path(__file__).resolve().parent.parent / 'anteprima.html'
fuori.write_text(pagina, encoding='utf-8')
print(fuori, f'{len(pagina) / 1024:.0f} KB')
