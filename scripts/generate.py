#!/usr/bin/env python3
"""
Genera gli SVG del profilo GitHub. Solo libreria standard.

    python3 profile/scripts/generate.py            # dati veri dall'API
    python3 profile/scripts/generate.py --sample   # dati finti, per l'anteprima
    python3 profile/scripts/generate.py --out img  # cartella di destinazione

Ogni grafica esce in due varianti, `-dark` e `-light`: il README le mette in un
<picture>, e il browser ne scarica una sola.

Due trappole di determinismo, entrambe risolte qui. Senza, il workflow
notturno produce un commit ogni notte anche quando non è cambiato nulla:

1. La finestra dei contributi è ancorata a giorni UTC interi. Lasciata libera,
   `contributionsCollection` misura «l'ultimo anno» dall'istante della
   richiesta, e due esecuzioni a minuti di distanza spostano i giorni fra le
   settimane.
2. I repository sono filtrati a `privacy: PUBLIC`. Un token personale vede
   anche i privati, quello del workflow no: senza il filtro le percentuali dei
   linguaggi cambiano a seconda di chi esegue lo script.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import svgkit as sk
from svgkit import (TEMI, barra_cresce, battuto, comparso, larghezza,
                    pallino_vivo, taglia, testo, tracciata)

QUI = Path(__file__).resolve().parent
RADICE = QUI.parent

LARG = 860
MESI = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu',
        'lug', 'ago', 'set', 'ott', 'nov', 'dic']

QUERY = '''
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first:100, ownerAffiliations:OWNER, privacy:PUBLIC,
                 isFork:false, orderBy:{field:PUSHED_AT, direction:DESC}) {
      totalCount
      nodes {
        name
        languages(first:8, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
'''


# ------------------------------------------------------------------- dati

def finestra() -> tuple[str, str]:
    """365 giorni chiusi su giorni UTC interi: la stessa richiesta a ore
    diverse deve produrre gli stessi identici byte."""
    oggi = datetime.now(timezone.utc).date()
    da = oggi - timedelta(days=364)
    return f'{da.isoformat()}T00:00:00Z', f'{oggi.isoformat()}T23:59:59Z'


def interroga(login: str, token: str) -> dict:
    da, a = finestra()
    corpo = json.dumps({'query': QUERY,
                        'variables': {'login': login, 'from': da, 'to': a}}).encode()
    req = urllib.request.Request(
        'https://api.github.com/graphql', data=corpo,
        headers={'Authorization': f'Bearer {token}',
                 'Content-Type': 'application/json',
                 'User-Agent': f'{login}-profile-generator'})
    with urllib.request.urlopen(req, timeout=45) as r:
        risposta = json.loads(r.read())
    if 'errors' in risposta:
        raise RuntimeError(f"GraphQL: {risposta['errors']}")
    return risposta['data']['user']


def campione() -> dict:
    """Dati finti ma plausibili, deterministici. Servono solo all'anteprima."""
    oggi = datetime.now(timezone.utc).date()
    inizio = oggi - timedelta(days=364)
    inizio -= timedelta(days=(inizio.weekday() + 1) % 7)  # allinea a domenica

    giorni, seme = [], 12345
    for i in range(371):
        seme = (seme * 1103515245 + 12345) % (2 ** 31)
        d = inizio + timedelta(days=i)
        n = 0
        if d <= oggi:
            r = seme % 100
            n = 0 if r < 34 else (r % 7) + (9 if r > 92 else 0)
        giorni.append({'date': d.isoformat(), 'contributionCount': n})

    settimane = [{'contributionDays': giorni[i:i + 7]} for i in range(0, 371, 7)]
    return {
        'contributionsCollection': {'contributionCalendar': {
            'totalContributions': sum(g['contributionCount'] for g in giorni),
            'weeks': settimane}},
        'repositories': {'totalCount': 9, 'nodes': [
            {'name': 'shawe', 'languages': {'edges': [
                {'size': 1_390_000, 'node': {'name': 'TypeScript', 'color': '#3178c6'}},
                {'size': 152_000, 'node': {'name': 'PL/pgSQL', 'color': '#336790'}},
                {'size': 41_000, 'node': {'name': 'CSS', 'color': '#663399'}}]}},
            {'name': 'infra', 'languages': {'edges': [
                {'size': 88_000, 'node': {'name': 'Shell', 'color': '#89e051'}},
                {'size': 34_000, 'node': {'name': 'Python', 'color': '#3572A5'}}]}},
            {'name': 'mc-tools', 'languages': {'edges': [
                {'size': 120_000, 'node': {'name': 'Java', 'color': '#b07219'}},
                {'size': 22_000, 'node': {'name': 'Shell', 'color': '#89e051'}}]}},
        ]},
    }


def giorni_piatti(utente: dict) -> list[dict]:
    fuori = []
    for s in utente['contributionsCollection']['contributionCalendar']['weeks']:
        fuori.extend(s['contributionDays'])
    return fuori


def streak(giorni: list[dict]) -> dict:
    """
    Serie di giorni consecutivi con almeno un contributo.

    L'ultimo giorno viene ignorato se è ancora vuoto: alle 5 del mattino non
    hai ancora committato, e non ha senso azzerare una serie viva per questo.
    """
    utili = [g for g in giorni if g['date'] <= datetime.now(timezone.utc).date().isoformat()]
    if utili and utili[-1]['contributionCount'] == 0:
        utili = utili[:-1]

    mass = cur = 0
    m_da = m_a = c_da = None
    for g in utili:
        if g['contributionCount'] > 0:
            cur += 1
            if cur == 1:
                c_da = g['date']
            if cur > mass:
                mass, m_da, m_a = cur, c_da, g['date']
        else:
            cur, c_da = 0, None
    return {'attuale': cur, 'attuale_da': c_da,
            'massimo': mass, 'massimo_da': m_da, 'massimo_a': m_a}


def linguaggi(utente: dict, quanti: int = 6) -> list[dict]:
    byte: dict[str, int] = {}
    repo: dict[str, int] = {}
    colore: dict[str, str] = {}
    for r in utente['repositories']['nodes']:
        for e in r.get('languages', {}).get('edges', []):
            nome = e['node']['name']
            byte[nome] = byte.get(nome, 0) + e['size']
            repo[nome] = repo.get(nome, 0) + 1
            colore[nome] = e['node']['color'] or '#8b949e'
    totale = sum(byte.values()) or 1
    ordinati = sorted(byte.items(), key=lambda kv: -kv[1])[:quanti]
    return [{'nome': n, 'quota': b / totale, 'repo': repo[n], 'colore': colore[n]}
            for n, b in ordinati]


def data_it(iso: str | None) -> str:
    if not iso:
        return '—'
    d = datetime.fromisoformat(iso).date()
    return f'{d.day} {MESI[d.month - 1]}'


def mila(n: int) -> str:
    return f'{n:,}'.replace(',', '.')


# --------------------------------------------------------------- grafiche

def hero(p: dict, dati: dict, tema: dict) -> str:
    alt = 236
    out = [sk.apri(LARG, alt, (400, 600, 800), f"{p['nome']} — {p['utente']}")]

    # Cornice che si disegna. Perimetro esatto: serve alla dasharray.
    x0, y0, w, h = 1, 1, LARG - 2, alt - 2
    out.append(tracciata(
        f'M {x0 + 8} {y0} H {x0 + w - 8} A 8 8 0 0 1 {x0 + w} {y0 + 8} '
        f'V {y0 + h - 8} A 8 8 0 0 1 {x0 + w - 8} {y0 + h} H {x0 + 8} '
        f'A 8 8 0 0 1 {x0} {y0 + h - 8} V {y0 + 8} A 8 8 0 0 1 {x0 + 8} {y0}',
        tema['rule'], 1, 2 * (w + h), 0.0, 1.1))

    px = 30
    # Riga di stato
    out.append(pallino_vivo(px + 4, 34, 3.5, tema['ok'], 0.5))
    out.append(comparso(testo(px + 18, 38, 'online', 13, tema['ok'], 600), 0.55))

    # Le barre a destra non sono decorazione: sono le ultime cinque settimane
    # di attività vera. Un indicatore di segnale che segnala qualcosa.
    giorni = giorni_piatti(dati)
    sett = [sum(g['contributionCount'] for g in giorni[i:i + 7])
            for i in range(0, len(giorni), 7)][-5:]
    tetto = max(sett) or 1
    bx = LARG - px - 5 * 9
    for i, v in enumerate(sett):
        out.append(barra_cresce(bx + i * 9, 38, 5, 4 + 14 * (v / tetto),
                                tema['accent'], 0.75 + i * 0.07, 0.35, 1))
    et = 'ultime 5 settimane'
    out.append(comparso(testo(bx - 12 - larghezza(et, 11), 38, et, 11, tema['faint']), 0.8))

    # Nome
    out.append(battuto('nome', px, 92, p['utente'], 34, tema['ink'],
                       1.05, 0.75, 800, tema['accent']))
    sotto = f"{p['nome']}  ·  dal {p['dal']}  ·  {dati['repositories']['totalCount']} repo pubblici"
    out.append(comparso(testo(px, 116, sotto, 12.5, tema['muted']), 1.85))

    out.append(tracciata(f'M {px} 138 H {LARG - px}', tema['rule'], 1,
                         LARG - 2 * px, 1.95, 0.5))

    # MOTD
    for i, riga in enumerate(p['motd'][:3]):
        y = 164 + i * 21
        out.append(comparso(testo(px, y, '>', 12.5, tema['accent'], 600), 2.15 + i * 0.16))
        out.append(battuto(f'm{i}', px + 16, y, riga, 12.5, tema['muted'],
                           2.2 + i * 0.16, 0.42))

    out.append(sk.chiudi())
    return ''.join(out)


def stats(dati: dict, tema: dict) -> str:
    alt = 218
    giorni = giorni_piatti(dati)
    cal = dati['contributionsCollection']['contributionCalendar']
    s = streak(giorni)
    out = [sk.apri(LARG, alt, (400, 600, 800), 'Contributi, serie e andamento settimanale')]

    px = 4
    colonne = [
        (mila(cal['totalContributions']), 'contributi', 'ultimi 12 mesi'),
        (f"{s['attuale']}", 'giorni di fila',
         f"da {data_it(s['attuale_da'])}" if s['attuale'] else 'nessuna in corso'),
        (f"{s['massimo']}", 'serie più lunga',
         f"{data_it(s['massimo_da'])} → {data_it(s['massimo_a'])}"),
    ]
    passo = (LARG - 2 * px) / 3
    for i, (val, etichetta, nota) in enumerate(colonne):
        x = px + i * passo
        if i:
            out.append(tracciata(f'M {x - 18} 14 V 70', tema['rule'], 1, 56, 0.3 + i * 0.1, 0.4))
        out.append(comparso(testo(x, 48, val, 34, tema['accent'], 800), 0.25 + i * 0.12, 0.4, 6))
        out.append(comparso(testo(x, 66, etichetta, 12.5, tema['ink'], 600), 0.4 + i * 0.12))
        x_nota = x + larghezza(etichetta, 12.5) + 10
        spazio = (x + passo - 26) - x_nota
        out.append(comparso(testo(x_nota, 66, taglia(nota, 11.5, spazio), 11.5,
                                  tema['faint']), 0.48 + i * 0.12))

    # Sparkline settimanale. Colonne, non una linea: un giorno a zero è spazio
    # vuoto, mentre una spezzata inventerebbe i valori intermedi.
    sett = [sum(g['contributionCount'] for g in giorni[i:i + 7])
            for i in range(0, len(giorni), 7)][-52:]
    tetto = max(sett) or 1
    base, alto = 196, 92
    larg_col = (LARG - 2 * px) / 52
    for i, v in enumerate(sett):
        out.append(barra_cresce(px + i * larg_col, base, larg_col - 2.4,
                                alto * (v / tetto), tema['accent'],
                                0.55 + i * 0.012, 0.4, 1.5))
    out.append(tracciata(f'M {px} {base + 0.5} H {LARG - px}', tema['rule'], 1,
                         LARG - 2 * px, 0.5, 0.6))
    out.append(comparso(testo(px, 214, 'contributi per settimana', 11, tema['faint']), 1.2))
    picco = f'max {tetto} in una settimana'
    out.append(comparso(testo(LARG - px - larghezza(picco, 11), 214, picco, 11,
                              tema['faint']), 1.2))
    out.append(sk.chiudi())
    return ''.join(out)


def langs(dati: dict, tema: dict, nota: str = '') -> str:
    voci = linguaggi(dati)
    alt = 26 + len(voci) * 30 + (20 if nota else 0)
    out = [sk.apri(LARG, alt, (400, 600), 'Linguaggi più usati nei repository pubblici')]
    px, col_barra = 4, 250
    for i, l in enumerate(voci):
        y = 24 + i * 30
        inizio = 0.2 + i * 0.1
        out.append(comparso(testo(px, y, l['nome'], 13, tema['ink'], 600), inizio))
        quota = f"{l['quota'] * 100:.1f}%"
        out.append(comparso(testo(px + 150, y, quota, 13, tema['accent'], 600), inizio + 0.04))
        rep = f"{l['repo']} repo"
        out.append(comparso(testo(LARG - px - larghezza(rep, 11.5), y, rep, 11.5,
                                  tema['faint']), inizio + 0.04))

        piena = (LARG - px - col_barra - 90)
        out.append(f'<rect x="{col_barra}" y="{y - 9}" width="{piena:.1f}" height="8" '
                   f'rx="4" fill="{tema["grid0"]}"/>')
        out.append(f'<rect x="{col_barra}" y="{y - 9}" width="0" height="8" rx="4" '
                   f'fill="{l["colore"]}"><animate attributeName="width" '
                   f'to="{piena * l["quota"]:.1f}" begin="{inizio + 0.06:.2f}s" '
                   f'dur="0.6s" fill="freeze"/></rect>')

    # Uno scarto va spiegato dove si vede, non in fondo alla pagina: senza
    # questa riga il grafico contraddice l'hero e lo stack.
    if nota:
        out.append(comparso(testo(px, 24 + len(voci) * 30 + 6, nota, 11.5,
                                  tema['faint']), 0.2 + len(voci) * 0.1))
    out.append(sk.chiudi())
    return ''.join(out)


def anno(dati: dict, tema: dict) -> str:
    """
    L'anno, un quadrato per giorno, riempito in ordine cronologico.

    L'unica animazione della pagina che significa qualcosa di per sé: il tempo
    scorre da sinistra a destra, e le colonne si accendono in quell'ordine.
    """
    giorni = giorni_piatti(dati)
    settimane = (len(giorni) + 6) // 7
    x0, y0 = 4, 22
    # Il passo si ricava dalla larghezza disponibile invece di essere fisso:
    # così la griglia finisce esattamente dove finisce la sparkline sopra.
    gap = 3
    passo = (LARG - 2 * x0) / settimane
    cella = passo - gap
    y_leg = y0 + 7 * passo + 16
    alt = y_leg + 10
    out = [sk.apri(LARG, alt, (400,), "Un anno di contributi, un quadrato per giorno")]

    tetto = max((g['contributionCount'] for g in giorni), default=0) or 1
    scala = [tema['grid0'], tema['accent'] + '40', tema['accent'] + '80',
             tema['accent'] + 'c0', tema['accent']]
    oggi = datetime.now(timezone.utc).date().isoformat()
    mese_visto = None

    for i, g in enumerate(giorni):
        col, riga = divmod(i, 7)
        if g['date'] > oggi:
            continue
        n = g['contributionCount']
        liv = 0 if n == 0 else min(4, 1 + int(3 * (n / tetto)))
        x, y = x0 + col * passo, y0 + riga * passo
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{cella:.2f}" height="{cella:.2f}" rx="2.5" '
            f'fill="{scala[liv]}" opacity="0">'
            f'<animate attributeName="opacity" to="1" begin="{0.15 + col * 0.014:.2f}s" '
            f'dur="0.3s" fill="freeze"/></rect>')

        d = datetime.fromisoformat(g['date']).date()
        if riga == 0 and d.month != mese_visto:
            mese_visto = d.month
            out.append(comparso(testo(x, 14, MESI[d.month - 1], 10.5, tema['faint']),
                                0.15 + col * 0.014))

    out.append(comparso(testo(x0, y_leg, 'meno', 10.5, tema['faint']), 1.1))
    for i, c in enumerate(scala):
        out.append(comparso(f'<rect x="{x0 + 34 + i * 15}" y="{y_leg - 8}" width="10" '
                            f'height="10" rx="2" fill="{c}"/>', 1.1 + i * 0.04))
    out.append(comparso(testo(x0 + 34 + len(scala) * 15 + 6, y_leg, 'più', 10.5,
                              tema['faint']), 1.3))
    nota = f'{settimane} settimane · {sum(1 for g in giorni if g["contributionCount"])} giorni attivi'
    out.append(comparso(testo(LARG - 4 - larghezza(nota, 10.5), y_leg, nota, 10.5,
                              tema['faint']), 1.3))
    out.append(sk.chiudi())
    return ''.join(out)


def percorso(p: dict, tema: dict) -> str:
    voci = p['percorso']
    alt_voce = [46 + len(v['righe']) * 19 for v in voci]
    alt = sum(alt_voce) + 16
    out = [sk.apri(LARG, alt, (400, 600), 'Percorso: server di gioco, community competitive, software')]

    x_rail, x_testo = 122, 148
    out.append(tracciata(f'M {x_rail} 8 V {alt - 24}', tema['rule'], 1, alt, 0.15, 1.0))

    y = 20
    for i, v in enumerate(voci):
        inizio = 0.3 + i * 0.22
        attivo = v.get('stato') == 'attivo'
        colore_p = tema['ok'] if attivo else tema['faint']

        if attivo:
            out.append(pallino_vivo(x_rail, y - 4, 4, colore_p, inizio))
        else:
            out.append(comparso(f'<circle cx="{x_rail}" cy="{y - 4}" r="4" '
                                f'fill="{tema["surface"]}" stroke="{colore_p}" '
                                f'stroke-width="1.5"/>', inizio))

        out.append(comparso(testo(4, y, v['periodo'], 11.5, tema['faint']), inizio))
        out.append(comparso(testo(x_testo, y, v['titolo'], 15, tema['ink'], 600),
                            inizio + 0.05, 0.35, 4))
        out.append(comparso(testo(x_testo + larghezza(v['titolo'], 15) + 12, y,
                                  v['ruolo'], 11.5, tema['accent']), inizio + 0.1))
        for j, riga in enumerate(v['righe']):
            out.append(comparso(testo(x_testo, y + 22 + j * 19, riga, 12.5, tema['muted']),
                                inizio + 0.14 + j * 0.05))
        y += alt_voce[i]

    out.append(sk.chiudi())
    return ''.join(out)


def stack(p: dict, tema: dict) -> str:
    voci = p['competenze']
    alt = len(voci) * 26 + 12
    out = [sk.apri(LARG, alt, (400, 600), 'Strumenti e tecnologie')]
    for i, v in enumerate(voci):
        y = 20 + i * 26
        inizio = 0.2 + i * 0.08
        out.append(comparso(testo(4, y, v['voce'], 12, tema['accent'], 600), inizio))
        out.append(comparso(testo(126, y, v['valori'], 12.5, tema['muted']), inizio + 0.05))
        if i:
            out.append(tracciata(f'M 4 {y - 19} H {LARG - 4}', tema['rule'], 1,
                                 LARG - 8, inizio, 0.4))
    return ''.join(out) + sk.chiudi()


def titolo_sezione(parola: str, tema: dict) -> str:
    """Intestazione con il carattere della pagina: l'unico modo di non usare
    il font di GitHub. Il testo resta nell'alt per chi legge con lo schermo."""
    alt, dim = 30, 13
    out = [sk.apri(LARG, alt, (600,), parola)]
    w = larghezza(parola, dim)
    out.append(comparso(testo(4, 19, parola, dim, tema['accent'], 600), 0.05))
    out.append(tracciata(f'M {w + 18} 14 H {LARG - 4}', tema['rule'], 1,
                         LARG - w - 22, 0.15, 0.7))
    return ''.join(out) + sk.chiudi()


# ------------------------------------------------------------------- main

SEZIONI = ['percorso', 'attività', 'linguaggi', 'stack', 'contatti']

# Le parole accentate restano tali a schermo, ma non nei nomi dei file: un
# URL con un accento funziona finché qualcuno non lo ricodifica per sbaglio.
ACCENTI = str.maketrans('àáèéìíòóùúÀÁÈÉÌÍÒÓÙÚ', 'aaeeiioouuAAEEIIOOUU')


def slug(parola: str) -> str:
    return parola.translate(ACCENTI).replace(' ', '-')

# Le parole accentate restano tali a schermo, ma non nei nomi dei file: un
# URL con un accento funziona finché qualcuno non lo ricodifica per sbaglio.
ACCENTI = str.maketrans('àáèéìíòóùúÀÁÈÉÌÍÒÓÙÚ', 'aaeeiioouuAAEEIIOOUU')


def slug(parola: str) -> str:
    return parola.translate(ACCENTI).replace(' ', '-')


def marchia(svg: str, tema: dict) -> str:
    """
    Timbra le grafiche generate con `--sample`.

    Senza, l'anteprima è indistinguibile dal risultato vero: basta un `git
    push` prima di aver rigenerato e sul profilo finiscono numeri inventati,
    in silenzio. Meglio un timbro brutto che una bugia invisibile.
    """
    etichetta = 'dati campione'
    x = LARG - 4 - larghezza(etichetta, 9.5) - 10
    timbro = (f'<g opacity="0.85"><rect x="{x:.1f}" y="0" '
              f'width="{larghezza(etichetta, 9.5) + 10:.1f}" height="15" rx="3" '
              f'fill="{tema["accent"]}"/>'
              f'{testo(x + 5, 11, etichetta, 9.5, tema["surface"], 600)}</g>')
    return svg.replace('</svg>', timbro + '</svg>')


def figura(nome: str, alt: str, cartella: str) -> str:
    """
    Una grafica in due temi.

    <picture> è l'unico modo documentato da GitHub per cambiare immagine con
    il tema, e ne scarica una sola: il repository raddoppia, la pagina no.
    """
    return (f'<picture>\n'
            f'  <source media="(prefers-color-scheme: dark)" '
            f'srcset="{cartella}/{nome}-dark.svg">\n'
            f'  <img alt="{alt}" src="{cartella}/{nome}-light.svg" width="860">\n'
            f'</picture>')


def readme(p: dict, cartella: str) -> str:
    """
    Costruisce README.md.

    Nota di onestà, scritta qui perché è una scelta con un costo: le
    intestazioni sono immagini, quindi l'indice automatico del README resta
    vuoto e non esistono ancore di sezione. In cambio il titolo è nel
    carattere della pagina invece che in quello di GitHub. Il testo
    dell'intestazione vive nell'attributo alt, per chi legge con lo schermo.
    """
    c = p['contatti']
    righe = [figura('hero', f"{p['utente']} — {p['nome']}", cartella), '']

    if p.get('lede'):
        righe += ['> ' + p['lede'], '']

    def sezione(chiave: str, corpo: list[str]) -> None:
        righe.append(figura(f'h-{slug(chiave)}', chiave, cartella))
        righe.append('')
        righe.extend(corpo)
        righe.append('')

    sezione('percorso', [figura('path', 'Percorso professionale', cartella)])
    sezione('attività', [
        figura('stats', 'Contributi, serie e andamento settimanale', cartella),
        '',
        figura('year', 'Un anno di contributi, un quadrato per giorno', cartella),
    ])
    sezione('linguaggi', [figura('langs', 'Linguaggi nei repository pubblici', cartella)])
    sezione('stack', [figura('stack', 'Strumenti e tecnologie', cartella)])

    contatti = []
    if c.get('email'):
        contatti.append(f"[{c['email']}](mailto:{c['email']})")
    if c.get('portfolio'):
        contatti.append(f"[portfolio]({c['portfolio']})")
    if c.get('linkedin'):
        contatti.append(f"[LinkedIn]({c['linkedin']})")
    sezione('contatti', ['&nbsp;&nbsp;·&nbsp;&nbsp;'.join(contatti)] if contatti else [])

    righe += [
        '<sub>Le grafiche di questa pagina sono disegnate dal repository stesso: '
        'nessuna richiesta a servizi esterni, nessun widget che possa smettere di '
        'rispondere. Si rigenerano ogni notte con GitHub Actions — '
        f'<a href="scripts/generate.py">scripts/generate.py</a>.</sub>',
        '',
    ]
    return '\n'.join(righe)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sample', action='store_true',
                    help='usa dati finti invece di chiamare l\'API')
    ap.add_argument('--out', default='img',
                    help='cartella di destinazione degli SVG (default: img)')
    ap.add_argument('--readme', action='store_true',
                    help='riscrive anche README.md da profilo.json')
    args = ap.parse_args()

    p = json.loads((RADICE / 'profilo.json').read_text(encoding='utf-8'))
    login = os.environ.get('GH_LOGIN') or p['utente']

    if args.sample:
        dati = campione()
        print('Dati CAMPIONE: i numeri qui sotto non sono veri.')
    else:
        token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
        if not token:
            print('GITHUB_TOKEN mancante. Per un\'anteprima usa --sample.',
                  file=sys.stderr)
            return 2
        try:
            dati = interroga(login, token)
        except (urllib.error.URLError, RuntimeError) as e:
            # Meglio fallire che pubblicare numeri finti su un profilo.
            print(f'Interrogazione fallita: {e}', file=sys.stderr)
            return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    scritti = 0
    for nome_tema, tema in TEMI.items():
        grafiche = {
            'hero': hero(p, dati, tema),
            'stats': stats(dati, tema),
            'langs': langs(dati, tema, p.get('nota_linguaggi', '')),
            'year': anno(dati, tema),
            'path': percorso(p, tema),
            'stack': stack(p, tema),
        }
        for parola in SEZIONI:
            grafiche[f'h-{slug(parola)}'] = titolo_sezione(parola, tema)

        for nome, contenuto in grafiche.items():
            if args.sample and not nome.startswith('h-'):
                contenuto = marchia(contenuto, tema)
            (out / f'{nome}-{nome_tema}.svg').write_text(contenuto, encoding='utf-8')
            scritti += 1

    if args.readme:
        dove = out.parent / 'README.md'
        dove.write_text(readme(p, out.name), encoding='utf-8')
        print(f'  {dove} riscritto')

    cal = dati['contributionsCollection']['contributionCalendar']
    s = streak(giorni_piatti(dati))
    print(f'{scritti} file in {out}/')
    print(f"  contributi 12 mesi : {mila(cal['totalContributions'])}")
    print(f"  serie attuale      : {s['attuale']} giorni")
    print(f"  serie più lunga    : {s['massimo']} giorni")
    print(f"  linguaggi          : " +
          ', '.join(f"{l['nome']} {l['quota'] * 100:.0f}%" for l in linguaggi(dati)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
