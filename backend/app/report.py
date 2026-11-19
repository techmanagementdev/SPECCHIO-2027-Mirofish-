"""Report per il cliente generato automaticamente dalle risposte di un sondaggio.

Solo dati aggregati: nessun dato è mostrato per gruppi con meno di 10 risposte e le
risposte aperte non sono riportate.
"""
from __future__ import annotations

import json
import re
import secrets
import statistics
import time

from .importer import SOGLIA_ANONIMATO, _numero, leggi_csv
from .settings import DATA_DIR, _hash, _verifica_hash

REPORT_DIR = DATA_DIR / "report"
NON_RISPONDE = {"NS/NR", "NS", "NR", "NON SO", "NON RISPONDE", "N/A", "NA"}
SI_NO = {"Sì", "Si", "SI", "SÌ", "Y", "Yes", "No", "N", "NO"}
MULTIPLA = re.compile(r"^(.*?)\s*\[(.+)\]\s*$")
TECNICHE = re.compile(r"^(id|submitdate|lastpage|startlanguage|seed|startdate|datestamp|ipaddr|refurl|token|interviewtime|.*time)$", re.I)


def _scala(valori: list[float]) -> tuple[float, float]:
    lo, hi = min(valori), max(valori)
    if hi <= 5:
        return (0 if lo == 0 else 1), 5
    if hi <= 7:
        return (0 if lo == 0 else 1), 7
    if hi <= 10:
        return (0 if lo == 0 else 1), 10
    return lo, hi


def semaforo(punteggio: float) -> dict:
    if punteggio >= 70:
        return {"colore": "verde", "emoji": "🟢", "etichetta": "Punto di forza"}
    if punteggio >= 50:
        return {"colore": "giallo", "emoji": "🟡", "etichetta": "Da migliorare"}
    return {"colore": "rosso", "emoji": "🔴", "etichetta": "Criticità"}


def _breve(testo: str, n: int = 90) -> str:
    return testo if len(testo) <= n else testo[: n - 1].rstrip() + "…"


def genera(csv_testo: str, titolo: str, cliente: str, colonna_gruppo: str, colonne_clima: list[str],
           colonna_fiducia: str | None, etichette: dict[str, str] | None = None,
           opzioni: dict[str, dict[str, str]] | None = None) -> dict:
    etichette, opzioni = etichette or {}, opzioni or {}
    colonne, righe = leggi_csv(csv_testo)
    nome = lambda c: etichette.get(c) or etichette.get(c.split("[")[0]) or c  # noqa: E731
    gruppo_di = lambda r: opzioni.get(colonna_gruppo, {}).get((r.get(colonna_gruppo) or "").strip(), (r.get(colonna_gruppo) or "").strip() or "Non indicato")  # noqa: E731

    gruppi: dict[str, list[dict]] = {}
    for r in righe:
        gruppi.setdefault(gruppo_di(r), []).append(r)
    piccoli = [g for g, rr in gruppi.items() if len(rr) < SOGLIA_ANONIMATO]
    if piccoli:
        altri = [r for g in piccoli for r in gruppi.pop(g)]
        if len(altri) >= SOGLIA_ANONIMATO:
            gruppi["Altri"] = altri

    domande, categoriali = [], []
    multiple: dict[str, list[dict]] = {}
    for c in colonne:
        if c == colonna_gruppo or TECNICHE.match(c):
            continue
        mm = MULTIPLA.match(nome(c)) or MULTIPLA.match(c)
        pieni_c = [(r.get(c) or "").strip() for r in righe if (r.get(c) or "").strip()]
        if mm and pieni_c and set(pieni_c) <= SI_NO:
            if len(pieni_c) >= SOGLIA_ANONIMATO:
                si = sum(1 for v in pieni_c if v.upper() in {"SÌ", "SI", "Y", "YES"})
                multiple.setdefault(mm.group(1).strip(), []).append({"etichetta": mm.group(2).strip(), "quota": round(100 * si / len(pieni_c)), "n": len(pieni_c)})
            continue
        valori = [(r.get(c) or "").strip() for r in righe]
        pieni = [v for v in valori if v and v.upper() not in NON_RISPONDE]
        if len(pieni) < SOGLIA_ANONIMATO:
            continue
        numeri = [n for v in pieni if re.fullmatch(r"-?\d+([.,]\d+)?", v) and (n := _numero(v)) is not None]
        if len(numeri) / len(pieni) > 0.9 and max(numeri) <= 10:
            lo, hi = _scala(numeri)
            media = statistics.fmean(numeri)
            punteggio = round(100 * (media - lo) / (hi - lo), 1) if hi > lo else 50.0
            distr = {str(int(k)): sum(1 for n in numeri if int(n) == k) for k in range(int(lo), int(hi) + 1)}
            per_gruppo = {}
            for g, rr in gruppi.items():
                vv = [n for r in rr if (v := (r.get(c) or "").strip()) and re.fullmatch(r"-?\d+([.,]\d+)?", v) and (n := _numero(v)) is not None]
                if len(vv) >= SOGLIA_ANONIMATO:
                    per_gruppo[g] = round(100 * (statistics.fmean(vv) - lo) / (hi - lo), 1) if hi > lo else 50.0
            domande.append({
                "id": c, "testo": nome(c), "breve": _breve(nome(c), 70), "n": len(numeri),
                "media": round(media, 2), "scala": [lo, hi], "punteggio": punteggio,
                "favorevoli": round(100 * sum(1 for n in numeri if n >= hi - (1 if hi <= 7 else 2)) / len(numeri)),
                "critici": round(100 * sum(1 for n in numeri if n <= lo + (1 if hi <= 7 else 2)) / len(numeri)),
                "distribuzione": distr, "per_gruppo": per_gruppo, "clima": c in colonne_clima, "fiducia": c == colonna_fiducia,
                **semaforo(punteggio),
            })
        else:
            distinti = sorted(set(pieni))
            if 2 <= len(distinti) <= 12:
                mappa = opzioni.get(c, {})
                freq = {mappa.get(v, v): sum(1 for x in pieni if x == v) for v in distinti}
                freq = dict(sorted(freq.items(), key=lambda x: -x[1]))
                categoriali.append({"id": c, "testo": nome(c), "n": len(pieni),
                                    "voci": [{"etichetta": k, "quota": round(100 * v / len(pieni))} for k, v in freq.items()]})

    for domanda, voci in multiple.items():
        if len(voci) >= 2:
            categoriali.append({"id": domanda[:40], "testo": domanda, "n": max(v["n"] for v in voci), "multipla": True,
                                "voci": sorted(voci, key=lambda v: -v["quota"])})
    clima = [d for d in domande if d["clima"]] or domande
    indice = round(statistics.fmean(d["punteggio"] for d in clima), 1) if clima else None
    per_gruppo_indice = {}
    for g in gruppi:
        vals = [d["per_gruppo"][g] for d in clima if g in d["per_gruppo"]]
        if vals:
            per_gruppo_indice[g] = round(statistics.fmean(vals), 1)

    ordinate = sorted(domande, key=lambda d: -d["punteggio"])
    in_breve = []
    if indice is not None:
        s = semaforo(indice)
        in_breve.append({"emoji": {"verde": "😊", "giallo": "😐", "rosso": "😟"}[s["colore"]],
                         "titolo": f"Indice complessivo {round(indice)} su 100",
                         "testo": {"verde": "Il clima generale è positivo.", "giallo": "Il clima generale è discreto, con margini di miglioramento.",
                                   "rosso": "Il clima generale è critico: servono interventi."}[s["colore"]]})
    if ordinate:
        in_breve.append({"emoji": "💪", "titolo": "Il punto più forte", "testo": f"«{ordinate[0]['breve']}»: {round(ordinate[0]['punteggio'])} su 100."})
        in_breve.append({"emoji": "⚠️", "titolo": "Il punto più debole", "testo": f"«{ordinate[-1]['breve']}»: {round(ordinate[-1]['punteggio'])} su 100."})
    if len(per_gruppo_indice) >= 2:
        alto = max(per_gruppo_indice, key=per_gruppo_indice.get)
        basso = min(per_gruppo_indice, key=per_gruppo_indice.get)
        in_breve.append({"emoji": "👥", "titolo": "Il gruppo più soddisfatto e il più critico",
                         "testo": f"{alto} ({round(per_gruppo_indice[alto])}) e {basso} ({round(per_gruppo_indice[basso])}): {round(per_gruppo_indice[alto] - per_gruppo_indice[basso])} punti di distanza."})
    divario = None
    for d in domande:
        if len(d["per_gruppo"]) >= 2:
            gap = max(d["per_gruppo"].values()) - min(d["per_gruppo"].values())
            if divario is None or gap > divario[1]:
                divario = (d, gap)
    if divario and divario[1] >= 10:
        in_breve.append({"emoji": "↔️", "titolo": "Dove i gruppi la pensano più diversamente",
                         "testo": f"«{divario[0]['breve']}»: {round(divario[1])} punti tra il gruppo più favorevole e il meno favorevole."})

    return {
        "titolo": titolo, "cliente": cliente, "creato": time.strftime("%Y-%m-%d %H:%M"),
        "risposte": len(righe), "gruppo": nome(colonna_gruppo),
        "gruppi": [{"nome": g, "n": len(rr), "indice": per_gruppo_indice.get(g), **(semaforo(per_gruppo_indice[g]) if g in per_gruppo_indice else {})}
                   for g, rr in sorted(gruppi.items(), key=lambda x: -len(x[1]))],
        "indice": indice, "semaforo": semaforo(indice) if indice is not None else None,
        "in_breve": in_breve, "domande": ordinate, "categoriali": categoriali,
        "legenda": [{"emoji": "🟢", "testo": "Punto di forza: 70 o più su 100"}, {"emoji": "🟡", "testo": "Da migliorare: tra 50 e 70"},
                    {"emoji": "🔴", "testo": "Criticità: sotto 50"}],
        "nota": f"Dati aggregati: i gruppi con meno di {SOGLIA_ANONIMATO} risposte non sono mostrati. I punteggi riportano ogni scala su 0–100.",
    }


# ---------------------------------------------------------------- archivio
def salva(report: dict, codice: str | None = None) -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report.setdefault("id", secrets.token_urlsafe(8).replace("-", "x").replace("_", "y"))
    if codice:
        report["codice_hash"] = _hash(codice)
    (REPORT_DIR / f"{report['id']}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def carica(rid: str) -> dict | None:
    if not re.fullmatch(r"[A-Za-z0-9]{6,20}", rid or ""):
        return None
    f = REPORT_DIR / f"{rid}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def elenco() -> list[dict]:
    if not REPORT_DIR.exists():
        return []
    out = []
    for f in sorted(REPORT_DIR.glob("*.json"), key=lambda p: -p.stat().st_mtime):
        r = json.loads(f.read_text(encoding="utf-8"))
        out.append({"id": r["id"], "titolo": r["titolo"], "cliente": r.get("cliente", ""), "creato": r["creato"],
                     "risposte": r["risposte"], "mondo_id": r.get("mondo_id"), "ha_codice": bool(r.get("codice_hash"))})
    return out


def elimina(rid: str) -> bool:
    f = REPORT_DIR / f"{rid}.json"
    if re.fullmatch(r"[A-Za-z0-9]{6,20}", rid or "") and f.exists():
        f.unlink()
        return True
    return False


def verifica_codice(rid: str, codice: str) -> bool:
    r = carica(rid)
    return bool(r and r.get("codice_hash") and _verifica_hash(codice, r["codice_hash"]))


def pubblico(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "codice_hash"}
