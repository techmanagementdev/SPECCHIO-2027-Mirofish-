"""Motore di simulazione: reazione individuale + diffusione per round + più esecuzioni.

Modello in breve
1. Ogni agente parte con un atteggiamento verso il mittente (dalla persona, con variazioni).
2. Il messaggio arriva tramite un canale: la probabilità di essere raggiunti e il peso
   della credibilità dipendono da quanto la persona si fida di quel canale.
3. La reazione individuale dipende da temi toccati e sensibilità della persona, stile del
   messaggio (concretezza, ascolto, enfasi, incertezza), fiducia e scetticismo.
   Con un modello linguistico configurato, la reazione di ogni persona è generata dal modello.
4. Nei round successivi la notizia passa di bocca in bocca: chi non era stato raggiunto
   la riceve deformata dal passaparola; chi era già informato si avvicina all'opinione dei
   contatti, con un peso maggiore per le opinioni negative.
5. Si ripete con semi diversi (almeno 3 esecuzioni) e si riportano media e fascia min-max.

I risultati sono esplorativi: indicano direzioni e ordini di grandezza, non stime di consenso.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass

from . import llm
from .analyzer import Analisi, analizza, nome_tema
from .world import CANALE_PASSAPAROLA, Agente, costruisci_popolazione

POS, NEG = 0.2, -0.2


@dataclass
class Richiesta:
    mondo: dict
    messaggio: str
    canale: str
    unita_bersaglio: list[str] | None = None
    composizione: dict | None = None
    round: int = 8
    esecuzioni: int = 3
    seme: int = 7
    usa_llm: bool = False


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def reazione_base(p: dict, a: Analisi) -> float:
    """Reazione della persona (senza rumore e senza canale) da -1 a 1."""
    sens = p.get("sensibilita", {})
    if a.temi:
        pesi = [(sens.get(t, 0.3), v) for t, v in a.temi.items()]
        somma = sum(w for w, _ in pesi) or 1
        tema = sum(w * v for w, v in pesi) / somma * min(1.0, 0.45 + somma / 2)
        tema *= 0.7 + 0.6 * a.concretezza  # i fatti concreti rendono credibile il contenuto, in bene e in male
        tema -= 0.15 * p["scetticismo"] * max(sens.get(t, 0.3) for t in a.temi)  # ogni cambiamento genera diffidenza
    else:
        tema = 0.25 * a.verso_generale
    testo = a.testo
    posizione = sum(v for k, v in p.get("posizioni", {}).items() if k in testo)
    tema += 0.6 * max(-1.0, min(1.0, posizione))  # posizioni specifiche della persona su parole chiave
    stile = (0.08 * a.concretezza + 0.22 * a.ascolto * (1 - p["fiducia"]) * 1.4
             - 0.4 * a.enfasi * p["scetticismo"] - 0.25 * a.incertezza * p["scetticismo"]
             + 0.15 * (a.chiarezza - 0.7))
    return _clip(tema + stile)


def _modula(r: float, fiducia: float, credibilita: float) -> float:
    r = r * (0.55 + 0.9 * fiducia) if r > 0 else r * (1.45 - 0.9 * fiducia)
    return r * (0.5 + 0.8 * credibilita)


def _stato(agenti: list[Agente]) -> dict:
    inf = [a for a in agenti if a.informato]
    s = [a.sentiment for a in inf]
    n = len(agenti) or 1
    media = statistics.fmean(s) if s else 0.0
    return {
        "informati": round(100 * len(inf) / n, 1),
        "indice": round((media + 1) * 50, 1),
        "positivi": round(100 * sum(1 for x in s if x > POS) / n, 1),
        "negativi": round(100 * sum(1 for x in s if x < NEG) / n, 1),
        "neutri": round(100 * sum(1 for x in s if NEG <= x <= POS) / n, 1),
    }


def _unita(agenti: list[Agente]) -> dict:
    out: dict[str, dict] = {}
    for a in agenti:
        u = out.setdefault(a.unita_id, {"pos": 0, "neu": 0, "neg": 0, "non": 0, "somma": 0.0, "inf": 0})
        if not a.informato:
            u["non"] += 1
        else:
            u["inf"] += 1
            u["somma"] += a.sentiment
            u["pos" if a.sentiment > POS else "neg" if a.sentiment < NEG else "neu"] += 1
    for u in out.values():
        u["indice"] = round(((u["somma"] / u["inf"]) + 1) * 50, 1) if u["inf"] else None
        del u["somma"]
    return out


def esegui_una(req: Richiesta, reazioni_llm: dict | None, seme: int) -> dict:
    rng = random.Random(seme)
    mondo = req.mondo
    personas = {p["id"]: p for p in mondo["personas"]}
    analisi = analizza(req.messaggio)
    agenti = costruisci_popolazione(mondo, req.composizione, rng)
    bersaglio = set(req.unita_bersaglio or [])

    def reazione(ag: Agente, canale: str) -> float:
        p = personas[ag.persona_id]
        cred = p.get("canali", {}).get(canale, 0.4)
        if reazioni_llm and ag.persona_id in reazioni_llm:
            r = reazioni_llm[ag.persona_id]["punteggio"] / 100 * (0.6 + 0.6 * cred)
        else:
            base = reazione_base({**p, "fiducia": ag.fiducia, "scetticismo": ag.scetticismo}, analisi)
            r = _modula(base, ag.fiducia, cred)
        return _clip(0.4 * ag.atteggiamento + r + ag.bias + rng.gauss(0, 0.08))

    # round 0: il messaggio arriva dal canale scelto
    for ag in agenti:
        p = personas[ag.persona_id]
        cred = p.get("canali", {}).get(req.canale, 0.4)
        prob = 0.05 + 0.9 * cred
        if bersaglio and ag.unita_id not in bersaglio:
            prob *= 0.15
        if rng.random() < prob:
            ag.informato, ag.via = True, req.canale
            ag.sentiment = ag.propria = reazione(ag, req.canale)

    storia = [_stato(agenti)]
    unita_storia = [_unita(agenti)]
    voci = 0
    for _ in range(req.round):
        nuovi: list[tuple[Agente, float]] = []
        for ag in agenti:
            if not ag.informato:
                continue
            cond = 0.15 + 0.55 * ag.influenza * min(1.0, abs(ag.sentiment) + 0.3)
            if reazioni_llm and ag.persona_id in reazioni_llm:
                cond = 0.5 * cond + 0.5 * reazioni_llm[ag.persona_id]["condivisione"] * 0.7
            if rng.random() > cond:
                continue
            for j in ag.vicini:
                v = agenti[j]
                if not v.informato:
                    propria = reazione(v, CANALE_PASSAPAROLA)
                    s = _clip(0.6 * propria + 0.4 * ag.sentiment - 0.08)  # il passaparola deforma, di solito in peggio
                    if ag.sentiment < -0.3:
                        voci += 1
                    nuovi.append((v, s))
                elif abs(ag.sentiment - v.sentiment) < 0.9:  # si ascolta solo chi non la pensa all'opposto
                    peso = 1.3 if ag.sentiment < 0 else 1.0
                    alfa = 0.08 * (1 - 0.5 * v.scetticismo) * peso
                    s = v.sentiment + alfa * (ag.sentiment - v.sentiment)
                    v.sentiment = _clip(0.9 * s + 0.1 * v.propria)  # ognuno resta ancorato alla propria idea
        for v, s in nuovi:
            if not v.informato:
                v.informato, v.via, v.sentiment, v.propria = True, CANALE_PASSAPAROLA, s, s
        storia.append(_stato(agenti))
        unita_storia.append(_unita(agenti))

    per_persona: dict[str, dict] = {}
    for ag in agenti:
        d = per_persona.setdefault(ag.persona_id, {"n": 0, "inf": 0, "somma": 0.0, "neg": 0, "pos": 0, "passaparola": 0})
        d["n"] += 1
        if ag.informato:
            d["inf"] += 1
            d["somma"] += ag.sentiment
            d["neg"] += ag.sentiment < NEG
            d["pos"] += ag.sentiment > POS
            d["passaparola"] += ag.via == CANALE_PASSAPAROLA
    return {"storia": storia, "unita": unita_storia, "per_persona": per_persona, "voci": voci, "n_agenti": len(agenti)}


def _obiezioni(mondo: dict, analisi: Analisi, per_persona: dict, canale: str, reazioni_llm: dict | None) -> list[dict]:
    personas = {p["id"]: p for p in mondo["personas"]}
    peso: dict[str, float] = {}
    for pid, d in per_persona.items():
        p = personas[pid]
        if reazioni_llm and pid in reazioni_llm and reazioni_llm[pid]["obiezione"]:
            testo = "«" + reazioni_llm[pid]["obiezione"].strip('«»" ') + "»"
            peso[testo] = peso.get(testo, 0) + d["neg"] + 0.3 * d["inf"]
            continue
        temi_neg = sorted(analisi.temi.items(), key=lambda x: x[1])[:2] or [("generale", 0)]
        for t, v in temi_neg:
            testo = p.get("obiezioni", {}).get(t) or p.get("obiezioni", {}).get("generale")
            if testo:
                peso[testo] = peso.get(testo, 0) + d["neg"] * (1.2 if v < 0 else 0.7) + 0.1 * d["inf"]
    stile = []
    scettici = sum(d["inf"] for pid, d in per_persona.items() if personas[pid]["scetticismo"] > 0.55)
    if analisi.enfasi > 0.2:
        stile.append(("«Sembra propaganda: troppi aggettivi, pochi fatti»", scettici * analisi.enfasi * 1.5))
    if analisi.concretezza < 0.25:
        stile.append(("«Belle parole, ma quando e come?»", scettici * 0.5 + 3))
    if analisi.incertezza > 0.2:
        stile.append(("«Non hanno ancora deciso niente»", scettici * analisi.incertezza))
    if canale in {"email", "bacheca", "comunicato"}:
        stile.append(("«Una comunicazione calata dall'alto, senza confronto»", scettici * 0.3))
    for t, w in stile:
        peso[t] = peso.get(t, 0) + w
    tot = sum(peso.values()) or 1
    top = sorted(peso.items(), key=lambda x: -x[1])[:5]
    return [{"testo": t, "quota": round(100 * w / tot)} for t, w in top if w > 0]


def _frasi(mondo: dict, per_persona: dict, analisi: Analisi, reazioni_llm: dict | None, rng: random.Random) -> list[dict]:
    personas = {p["id"]: p for p in mondo["personas"]}
    tema = nome_tema(next(iter(sorted(analisi.temi, key=lambda t: abs(analisi.temi[t]), reverse=True)), "")) or "questa novità"
    out = []
    for pid, d in sorted(per_persona.items(), key=lambda x: -x[1]["inf"])[:6]:
        if not d["inf"]:
            continue
        media = d["somma"] / d["inf"]
        p = personas[pid]
        if reazioni_llm and pid in reazioni_llm and reazioni_llm[pid]["frase"]:
            testo = reazioni_llm[pid]["frase"]
        else:
            chiave = "positiva" if media > POS else "negativa" if media < NEG else "neutra"
            opzioni = p.get("frasi", {}).get(chiave) or ["Vediamo cosa succede davvero."]
            testo = rng.choice(opzioni).replace("{tema}", tema)
        out.append({"persona_id": pid, "persona": p["nome"], "tono": "positivo" if media > POS else "negativo" if media < NEG else "neutro", "testo": testo})
    return out


VOCI = {
    "turni": "Gira voce che i turni cambieranno per tutti, anche per chi non è coinvolto.",
    "organizzazione": "Si dice che dietro la riorganizzazione ci siano tagli di personale.",
    "retribuzione": "C'è chi dice che il premio andrà solo a pochi.",
    "welfare": "Dicono che il welfare costerà qualcosa a chi lo usa.",
    "cantieri": "Si dice che i lavori dureranno molto più del previsto.",
    "tariffe": "Gira voce che dopo l'annuncio arriveranno aumenti.",
    "strumenti": "Si dice che il nuovo strumento servirà a controllare chi lavora.",
    "traffico": "Dicono che i camion verranno deviati nei centri abitati.",
    "servizi": "Si dice che il servizio verrà spostato altrove.",
}


def _consigli(mondo: dict, req: Richiesta, analisi: Analisi, finale: dict, per_persona: dict, voci: float) -> list[str]:
    personas = {p["id"]: p for p in mondo["personas"]}
    canali = {c["id"]: c["nome"] for c in mondo["canali"]}
    out = []
    raggiunti_subito = finale["raggiunti_canale"]
    if raggiunti_subito < 50:
        migliore = max(mondo["canali"], key=lambda c: statistics.fmean(p.get("canali", {}).get(c["id"], 0.4) for p in mondo["personas"]))
        out.append(f"Il canale «{canali.get(req.canale, req.canale)}» raggiunge direttamente solo il {raggiunti_subito:.0f}%: prova «{migliore['nome']}».")
    peggiori = sorted(((d["somma"] / d["inf"], pid) for pid, d in per_persona.items() if d["inf"]), key=lambda x: x[0])[:1]
    for media, pid in peggiori:
        if media < 0:
            out.append(f"Il gruppo più critico è «{personas[pid]['nome']}»: coinvolgilo prima dell'annuncio, con un canale di cui si fida.")
    if analisi.concretezza < 0.3:
        out.append("Aggiungi date, numeri e chi fa cosa: la concretezza riduce lo scetticismo.")
    if analisi.enfasi > 0.2:
        out.append("Togli i superlativi: con i profili scettici l'enfasi fa perdere credibilità.")
    if analisi.ascolto < 0.2 and finale["negativi"] > 20:
        out.append("Aggiungi un modo concreto per rispondere o proporre: chi si sente ascoltato critica meno.")
    if voci > 15:
        out.append("Il passaparola genera voci negative: anticipa cosa NON cambia e chi è escluso.")
    if not out:
        out.append("Messaggio solido: verificalo con una breve domanda reale prima della diffusione.")
    return out[:4]


def simula(req: Richiesta) -> dict:
    mondo = req.mondo
    analisi = analizza(req.messaggio)
    canale_nome = next((c["nome"] for c in mondo["canali"] if c["id"] == req.canale), req.canale)
    reazioni_llm = None
    errore_llm = None
    if req.usa_llm and llm.disponibile():
        reazioni_llm = {}
        try:
            for p in mondo["personas"]:
                reazioni_llm[p["id"]] = llm.reazione_persona(p, mondo.get("contesto", ""), req.messaggio, canale_nome)
        except Exception as e:  # il modello non risponde: si torna alle regole
            errore_llm = str(e)[:200]
            reazioni_llm = None

    runs = [esegui_una(req, reazioni_llm, req.seme + 101 * i) for i in range(max(1, req.esecuzioni))]
    R = len(runs[0]["storia"])
    serie = {}
    for k in ["indice", "informati", "positivi", "negativi", "neutri"]:
        serie[k] = {
            "media": [round(statistics.fmean(r["storia"][t][k] for r in runs), 1) for t in range(R)],
            "min": [min(r["storia"][t][k] for r in runs) for t in range(R)],
            "max": [max(r["storia"][t][k] for r in runs) for t in range(R)],
        }

    per_persona: dict[str, dict] = {}
    for r in runs:
        for pid, d in r["per_persona"].items():
            acc = per_persona.setdefault(pid, {"n": 0, "inf": 0, "somma": 0.0, "neg": 0, "pos": 0, "passaparola": 0})
            for k in acc:
                acc[k] += d[k]
    personas = {p["id"]: p for p in mondo["personas"]}
    tabella_personas = []
    for pid, d in per_persona.items():
        media = d["somma"] / d["inf"] if d["inf"] else None
        partenza = 0.4 * personas[pid]["atteggiamento"]
        tabella_personas.append({
            "id": pid, "nome": personas[pid]["nome"], "colore": personas[pid].get("colore", "#888"),
            "agenti": round(d["n"] / len(runs)),
            "indice": round((media + 1) * 50, 1) if media is not None else None,
            "partenza": round((partenza + 1) * 50, 1),
            "informati": round(100 * d["inf"] / d["n"], 1) if d["n"] else 0,
            "negativi": round(100 * d["neg"] / d["inf"], 1) if d["inf"] else 0,
            "positivi": round(100 * d["pos"] / d["inf"], 1) if d["inf"] else 0,
            "da_passaparola": round(100 * d["passaparola"] / d["inf"], 1) if d["inf"] else 0,
            "reazione_llm": (reazioni_llm or {}).get(pid),
        })
    tabella_personas.sort(key=lambda x: x["indice"] if x["indice"] is not None else 50)

    finali = [r["storia"][-1]["indice"] for r in runs]
    finale = {k: serie[k]["media"][-1] for k in serie}
    finale["raggiunti_canale"] = serie["informati"]["media"][0]
    finale["dispersione"] = round(max(finali) - min(finali), 1)
    finale["stabilita"] = "alta" if finale["dispersione"] < 4 else "media" if finale["dispersione"] < 8 else "bassa"
    voci_medie = statistics.fmean(r["voci"] for r in runs)
    rng = random.Random(req.seme)

    stelle = 3 if finale["indice"] >= 62 and finale["negativi"] < 20 else 2 if finale["indice"] >= 52 and finale["negativi"] < 35 else 1
    voci_testi = []
    if voci_medie > 0.06 * runs[0]["n_agenti"] and finale["negativi"] > 10:
        temi_neg = [t for t, v in sorted(analisi.temi.items(), key=lambda x: x[1]) if t in VOCI]
        voci_testi = [VOCI[t] for t in temi_neg[:2]] or ["Gira voce che dietro l'annuncio ci sia qualcosa che non viene detto."]

    return {
        "mondo_id": mondo["id"],
        "messaggio": req.messaggio,
        "canale": {"id": req.canale, "nome": canale_nome},
        "modalita": "modello linguistico" if reazioni_llm else "regole (dimostrativa)",
        "errore_llm": errore_llm,
        "analisi": analisi.to_dict(),
        "serie": serie,
        "finale": finale,
        "unita": runs[0]["unita"],
        "personas": tabella_personas,
        "obiezioni": _obiezioni(mondo, analisi, per_persona, req.canale, reazioni_llm),
        "frasi": _frasi(mondo, per_persona, analisi, reazioni_llm, rng),
        "voci": voci_testi,
        "consigli": _consigli(mondo, req, analisi, finale, per_persona, voci_medie),
        "stelle": stelle,
        "xp": 10 + 10 * stelle,
        "agenti": runs[0]["n_agenti"],
        "esecuzioni": len(runs),
        "avvertenza": "Simulazione esplorativa su personas sintetiche: indica direzioni e ordini di grandezza, non è una previsione validata né un sondaggio.",
    }
