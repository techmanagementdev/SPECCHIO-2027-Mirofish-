"""Crea un mondo a partire da un CSV esportato da LimeSurvey (o da qualsiasi tabella).

Regole di tutela, coerenti con le proposte EMI/Quaeris:
- si usano solo medie per gruppo, mai risposte individuali;
- i gruppi con meno di 10 risposte sono accorpati in «Altri»;
- il file caricato non viene salvato: si salva solo il mondo con le medie.
"""
from __future__ import annotations

import csv
import io
import re
import statistics

SOGLIA_ANONIMATO = 10
COLORI = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948", "#5f5e5a", "#185fa5", "#993c1d", "#0f6e56"]


def _numero(v: str) -> float | None:
    v = (v or "").strip().replace(",", ".")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        m = re.match(r"^[A-Za-z]*0*(\d+)$", v)  # codici tipo A1, A2
        return float(m.group(1)) if m else None


def leggi_csv(testo: str) -> tuple[list[str], list[dict]]:
    campione = testo[:5000]
    sep = ";" if campione.count(";") > campione.count(",") else ","
    reader = csv.DictReader(io.StringIO(testo), delimiter=sep)
    righe = list(reader)
    return list(reader.fieldnames or []), righe


def anteprima(testo: str) -> dict:
    colonne, righe = leggi_csv(testo)
    numeriche, categoriche = [], []
    for c in colonne:
        valori = [r.get(c, "") for r in righe if (r.get(c) or "").strip()]
        if not valori:
            continue
        nums = [_numero(v) if re.fullmatch(r"\s*-?\d+([.,]\d+)?\s*", v) else None for v in valori]
        quota = sum(n is not None for n in nums) / len(valori)
        distinti = len(set(valori))
        if quota > 0.9 and distinti > 1:
            vv = [n for n in nums if n is not None]
            if 0 <= min(vv) and max(vv) <= 10:
                numeriche.append(c)
        if 2 <= distinti <= 15 and quota < 0.9 or (2 <= distinti <= 8):
            categoriche.append(c)
    categoriche.sort(key=lambda c: c in numeriche)  # prima le colonne testuali
    return {"colonne": colonne, "righe": len(righe), "numeriche": numeriche, "categoriche": categoriche}


def crea_mondo(testo: str, nome: str, colonna_gruppo: str, colonne_clima: list[str], colonna_fiducia: str | None,
               modello: dict) -> dict:
    """modello: mondo di partenza da cui prendere canali, contesto e parametri delle personas."""
    _, righe = leggi_csv(testo)
    gruppi: dict[str, list[dict]] = {}
    for r in righe:
        g = (r.get(colonna_gruppo) or "").strip() or "Non indicato"
        gruppi.setdefault(g, []).append(r)
    piccoli = [g for g, rr in gruppi.items() if len(rr) < SOGLIA_ANONIMATO]
    if piccoli:
        altri = [r for g in piccoli for r in gruppi.pop(g)]
        if len(altri) >= SOGLIA_ANONIMATO:
            gruppi["Altri"] = altri

    def norm(col: str, valori: list[float]) -> float:
        tutti = [n for r in righe if (n := _numero(r.get(col, ""))) is not None]
        lo, hi = min(tutti), max(tutti)
        return (statistics.fmean(valori) - lo) / (hi - lo) if hi > lo else 0.5

    base = modello["personas"][0]
    personas, composizione = [], {}
    for i, (g, rr) in enumerate(sorted(gruppi.items(), key=lambda x: -len(x[1]))):
        clima = []
        for c in colonne_clima:
            vals = [n for r in rr if (n := _numero(r.get(c, ""))) is not None]
            if vals:
                clima.append(norm(c, vals))
        livello = statistics.fmean(clima) if clima else 0.5
        if colonna_fiducia:
            vals = [n for r in rr if (n := _numero(r.get(colonna_fiducia, ""))) is not None]
            fiducia = norm(colonna_fiducia, vals) if vals else livello
        else:
            fiducia = livello
        pid = re.sub(r"[^a-z0-9]+", "-", g.lower()).strip("-") or f"gruppo-{i}"
        personas.append({
            "id": pid, "nome": g, "categoria": g, "colore": COLORI[i % len(COLORI)],
            "avatar": "".join(w[0] for w in g.split()[:2]).upper() or "G",
            "descrizione": f"Persona costruita dalle medie di {len(rr)} risposte del gruppo «{g}». Clima medio {round(livello * 10, 1)}/10.",
            "atteggiamento": round(2 * livello - 1, 2), "fiducia": round(fiducia, 2),
            "scetticismo": round(1 - fiducia * 0.8, 2), "influenza": 0.5,
            "sensibilita": base.get("sensibilita", {}), "canali": base.get("canali", {}),
            "criticita": [], "aspettative": [],
            "frasi": base.get("frasi", {}), "obiezioni": {"generale": "«Vediamo se cambia davvero qualcosa»"},
            "voce": "concreta",
        })
        composizione[pid] = len(rr)
    mid = "utente-" + re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    return {
        "id": mid, "nome": nome, "tipo": modello.get("tipo", "organizzazione"),
        "descrizione": f"Mondo creato da file: {sum(composizione.values())} risposte, {len(personas)} gruppi (soglia di anonimato {SOGLIA_ANONIMATO}).",
        "contesto": modello.get("contesto", ""), "etichetta_unita": "Gruppo",
        "unita": [{"id": "tutti", "nome": "Tutti"}], "canali": modello["canali"],
        "personas": personas, "composizione": {"tutti": composizione},
        "missioni": [], "esempi": modello.get("esempi", []),
    }


def rinomina_valori(testo: str, colonna: str, mappa: dict[str, str]) -> str:
    """Sostituisce i codici di risposta di una colonna con i testi (es. A1 -> Operativi su strada)."""
    if not mappa:
        return testo
    sep = ";" if testo[:5000].count(";") > testo[:5000].count(",") else ","
    reader = csv.DictReader(io.StringIO(testo), delimiter=sep)
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=reader.fieldnames, delimiter=sep)
    w.writeheader()
    for r in reader:
        v = (r.get(colonna) or "").strip()
        if v in mappa and mappa[v]:
            r[colonna] = mappa[v]
        w.writerow(r)
    return out.getvalue()
