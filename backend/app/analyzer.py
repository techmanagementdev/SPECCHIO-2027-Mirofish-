"""Analisi del messaggio: temi toccati, verso (positivo/negativo) per tema e stile.

Funziona senza modello linguistico. Quando un modello è configurato, le reazioni
delle personas sono generate dal modello e questa analisi resta come supporto
per i consigli e le obiezioni di stile.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TEMI: dict[str, dict] = {
    "turni": {"nome": "turni e orari", "kw": ["turn", "orari ", "orario", "reperibil", "ferie", "riposi", "lavoro notturno"], "tipo": "misto"},
    "sicurezza": {"nome": "sicurezza", "kw": ["sicurezz", "incident", "infortun", "dpi", "rischi", "sinistr"], "tipo": "beneficio"},
    "welfare": {"nome": "welfare", "kw": ["welfare", "buoni pasto", "buono pasto", "benefit", "conciliaz", "smart working", "lavoro agile", "assicurazion"], "tipo": "beneficio"},
    "retribuzione": {"nome": "retribuzione", "kw": ["stipend", "retribu", "premio", "premi di", "salari", "bonus", "produttivit", "busta paga"], "tipo": "beneficio"},
    "carriera": {"nome": "crescita e formazione", "kw": ["carrier", "formazion", "crescit", "promozion", " corsi di", "corsi ", "competenz"], "tipo": "beneficio"},
    "strumenti": {"nome": "strumenti e mezzi", "kw": ["strument", "mezzi di lavoro", "veicol", " app", "digital", "software", "tablet", "attrezz", "dotazion", "furgon"], "tipo": "beneficio"},
    "organizzazione": {"nome": "riorganizzazione", "kw": ["riorganizz", "ristruttur", "accorpa", "trasferiment", "nuovo modello", "organigramma", "esternalizz", "unificaz"], "tipo": "cambiamento"},
    "ascolto": {"nome": "ascolto e coinvolgimento", "kw": ["ascolt", "confront", "proposte", "partecip", "insieme", "coinvolg", "dialogo", "feedback", "suggeriment", "segnalazion", "ci rivedremo", "tavolo", "incontri"], "tipo": "beneficio"},
    "cantieri": {"nome": "cantieri e lavori", "kw": ["cantier", "lavori", "terza corsia", "deviazion", "restringiment", "chiusur"], "tipo": "costo"},
    "tariffe": {"nome": "tariffe e prezzi", "kw": ["pedagg", "tariff", "prezz", "scont", " costa ", " costerà", "costo", "costi", "tasse", "tassa", " imu", " tari ", "bollett", " euro", "€"], "tipo": "costo"},
    "traffico": {"nome": "traffico e viabilità", "kw": ["traffic", "code ", "coda", "congestion", "mezzi pesanti", "camion", "viabilit", "parchegg", "ztl", "zona a traffico limitato"], "tipo": "costo"},
    "ambiente": {"nome": "ambiente", "kw": ["ambient", "rumor", "inquin", "verde", "alberi", "emission", " aria ", "barriere antirumore", "parco", "parchi"], "tipo": "misto"},
    "servizi": {"nome": "servizi pubblici", "kw": ["serviz", "sanit", "ospedal", "scuol", "asilo", "bibliotec", "sportell", "assistenza"], "tipo": "beneficio"},
    "casa": {"nome": "casa e affitti", "kw": ["casa", "case ", "affitt", "abitaz", "alloggi", "mutu"], "tipo": "beneficio"},
    "lavoro": {"nome": "lavoro e imprese", "kw": ["occupaz", "posti di lavoro", "assunzion", "impres", "aziende", "negozi", "commerc", "attività produttiv"], "tipo": "beneficio"},
    "frequenza": {"nome": "frequenza delle corse", "kw": ["frequen", "più corse", "nuove corse", "corse ogni", "ogni 10 minuti", "ogni 15 minuti", "ogni 20 minuti", "ogni 30 minuti", "corse notturne", "corse serali"], "tipo": "beneficio"},
    "puntualita": {"nome": "puntualità", "kw": ["puntual", "ritard", "in orario", "orari garantiti"], "tipo": "beneficio"},
    "comfort": {"nome": "comfort del viaggio", "kw": ["comfort", "wi-fi", "wifi", "aria condizionata", "climatizz", "posti a sedere", "bagagli", "mezzi nuovi", "autobus nuovi"], "tipo": "beneficio"},
    "biglietto": {"nome": "acquisto del biglietto", "kw": ["bigliett", "prenota", "acquist", "contactless", "carta di credito", "biglietteria"], "tipo": "beneficio"},
    "tempi": {"nome": "tempi di viaggio", "kw": ["tempo di viaggio", "più veloce", "veloci", "diretto", "diretta", "senza fermate intermedie", "in meno di"], "tipo": "beneficio"},
    "fermate": {"nome": "fermate e accessibilità", "kw": ["fermat", "capolinea", "accessib", "mobilità ridotta", "assistenza"], "tipo": "beneficio"},
    "trasporti": {"nome": "trasporto pubblico", "kw": ["autobus", " bus", "tram", "trasporto pubblico", "ciclabil", "bici", "treno", "navett"], "tipo": "beneficio"},
}

AUMENTO = ["aument", "rincar", "più ", "maggior", "potenzi", "rafforz", "estens", "raddopp", "nuov", "avranno", "avrete", "nascerà", "introdu", "attiver", "arriverà", "sarà disponibile", "collegherà", "metteremo a disposizione"]
RIDUZIONE = ["riduz", "ridott", "riduc", "diminu", " meno", "calo", "tagli", "sopprim", "eliminaz", "elimin", "sospens", "sospes"]
POSITIVI = ["miglior", "investiment", "gratuit", "sconto", "valorizz", "semplific", "garant", "tutel", "incentiv", "risparmi", "agevol", "stabilizz", "fine lavori", "conclusion", "completament", "riconosciment"]
MITIGAZIONE = ["controll", "solo fino", "mitigaz", "ristor", "barrier", "limitat", "riduzione dei disagi", "numero dedicato", "verific", "anticipo", "percorsi alternativi", "gratuit", "fermi", "invariat", "congelat"]
NEGATIVI = ["sacrific", "obbligatori", "sanzion", "ritard", "rinvi", "blocc", "esuber", "disagi", "penalizz", "costrett", "rincar"]
ENFASI = ["storic", "straordinar", "eccellenz", "il migliore", "rivoluzion", "unico in", "grandios", "senza precedenti", "epocal", "!"]
INCERTEZZA = ["valut", "potrebbe", "potranno", "forse", "eventual", "stiamo studiando", "ipotes", "in futuro", "prossimamente"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


@dataclass
class Analisi:
    temi: dict[str, float] = field(default_factory=dict)  # tema -> verso [-1, 1]
    concretezza: float = 0.0
    ascolto: float = 0.0
    enfasi: float = 0.0
    incertezza: float = 0.0
    chiarezza: float = 1.0
    parole: int = 0
    verso_generale: float = 0.0
    testo: str = ""

    def to_dict(self) -> dict:
        return {
            "temi": {k: {"nome": TEMI[k]["nome"], "verso": round(v, 2)} for k, v in self.temi.items()},
            "concretezza": round(self.concretezza, 2),
            "ascolto": round(self.ascolto, 2),
            "enfasi": round(self.enfasi, 2),
            "incertezza": round(self.incertezza, 2),
            "chiarezza": round(self.chiarezza, 2),
            "parole": self.parole,
            "verso_generale": round(self.verso_generale, 2),
        }


def _count(text: str, words: list[str]) -> int:
    return sum(text.count(w) for w in words)


def _frasi(text: str) -> list[str]:
    parti = re.split(r"(?<=[.;:?!])\s+|\n+", text)
    return [p for p in parti if p.strip()]


def analizza(messaggio: str) -> Analisi:
    testo = " " + messaggio.lower().replace("’", "'") + " "
    a = Analisi(parole=len(messaggio.split()), testo=testo)
    accum: dict[str, list[float]] = {}
    tot_generale = 0.0
    for frase in _frasi(testo):
        f = " " + frase + " "
        aum, rid = _count(f, AUMENTO), _count(f, RIDUZIONE)
        for x, y in re.findall(r"da (\d+(?:[.,]\d+)?) a (\d+(?:[.,]\d+)?)", f):  # «passa da 10 a 12 euro»
            vx, vy = float(x.replace(",", ".")), float(y.replace(",", "."))
            aum, rid = aum + (vy > vx), rid + (vy < vx)
        pos, neg = _count(f, POSITIVI), _count(f, NEGATIVI)
        generale = pos - neg
        tot_generale += generale
        mitiga = _count(f, MITIGAZIONE)
        presenti = [tid for tid, t in TEMI.items() if any(k in f for k in t["kw"])]
        ha_costo = any(TEMI[t]["tipo"] == "costo" for t in presenti)
        for tid, t in TEMI.items():
            if not any(k in f for k in t["kw"]):
                continue
            if t["tipo"] == "costo":
                direzione = -1
            elif t["tipo"] == "beneficio":
                direzione = 1
            elif t["tipo"] == "cambiamento":
                direzione = 0
            else:  # misto: dipende dalle parole
                direzione = -1 if any(w in f for w in ["rumor", "inquin", "notturn", "notti", "notte", "straordinar", "reperibil", "weekend", "festiv"]) else 1
            if ha_costo and t["tipo"] == "beneficio":
                verso = generale  # in una frase sui costi, aumenti e riduzioni si riferiscono al costo
            else:
                verso = generale + direzione * (aum - rid)
            if t["tipo"] == "costo" or (t["tipo"] == "misto" and direzione < 0):
                verso += 0.8 * mitiga
            if t["tipo"] == "cambiamento":
                verso -= 0.6  # il cambiamento organizzativo genera di per sé incertezza
            if tid == "cantieri" and any(w in f for w in ["fine lavori", "conclu", "completa", "termine dei lavori"]):
                verso += 1.5
            accum.setdefault(tid, []).append(verso)
    for tid, valori in accum.items():
        media = sum(valori) / len(valori)
        a.temi[tid] = max(-1.0, min(1.0, media / 1.5))
    a.verso_generale = max(-1.0, min(1.0, tot_generale / 3))

    cifre = len(re.findall(r"\d+", testo))
    date = _count(testo, MESI) + _count(testo, [" entro ", " dal ", " a partire da", " dalle ore", "settimana", "€", "%"])
    a.concretezza = min(1.0, 0.18 * cifre + 0.22 * date)
    a.ascolto = min(1.0, 0.35 * _count(testo, TEMI["ascolto"]["kw"]))
    a.enfasi = min(1.0, 0.3 * _count(testo, ENFASI))
    a.incertezza = min(1.0, 0.3 * _count(testo, INCERTEZZA))
    if a.parole < 12:
        a.chiarezza = 0.5
    elif a.parole > 160:
        a.chiarezza = max(0.3, 1 - (a.parole - 160) / 300)
    return a


def nome_tema(tid: str) -> str:
    return TEMI.get(tid, {}).get("nome", tid)
