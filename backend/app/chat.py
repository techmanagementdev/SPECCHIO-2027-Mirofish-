"""Dialogo con una persona di opinione."""
from __future__ import annotations

import random

from . import llm
from .analyzer import analizza, nome_tema
from .engine import reazione_base


def _top_canali(p: dict, mondo: dict, n: int = 2) -> list[str]:
    nomi = {c["id"]: c["nome"] for c in mondo["canali"]}
    nomi["passaparola"] = "passaparola"
    out = [nomi.get(k, k) for k, _ in sorted(p.get("canali", {}).items(), key=lambda x: -x[1])[:n]]
    return [x[:1].lower() + x[1:] if not x[:2].isupper() else x for x in out]


def risposta_regole(mondo: dict, p: dict, domanda: str, contesto_messaggio: str | None, seme: int) -> str:
    rng = random.Random(seme)
    q = domanda.lower()
    apertura = rng.choice(p.get("aperture") or ["Guardi,", "Le dico come la vedo:", "Sinceramente,"])
    if any(w in q for w in ["manca", "aspett", "ideale", "vorre", "miglior", "cambier"]):
        asp = p.get("aspettative", ["essere ascoltato"])
        return f"{apertura} mi aspetto soprattutto {asp[0]}" + (f", e poi {asp[1]}" if len(asp) > 1 else "") + "."
    if any(w in q for w in ["problem", "critic", "difficol", "pesa", "non va"]):
        cr = p.get("criticita", ["la poca chiarezza"])
        return f"{apertura} il problema principale è {cr[0]}" + (f". Poi c'è {cr[1]}" if len(cr) > 1 else "") + "."
    if any(w in q for w in ["informa", "canal", "come ti", "come le", "fonte", "fid"]):
        c = _top_canali(p, mondo)
        return f"{apertura} mi fido di più di {c[0]}" + (f" e di {c[1]}" if len(c) > 1 else "") + ". Le comunicazioni che arrivano dall'alto senza spiegazioni le leggo poco."
    a = analizza(domanda)
    if not a.temi and contesto_messaggio:
        a = analizza(contesto_messaggio)
    r = reazione_base(p, a) + 0.4 * p["atteggiamento"]
    tema = nome_tema(next(iter(sorted(a.temi, key=lambda t: abs(a.temi[t]), reverse=True)), "")) or "questa cosa"
    chiave = "positiva" if r > 0.2 else "negativa" if r < -0.2 else "neutra"
    frase = rng.choice(p.get("frasi", {}).get(chiave) or ["Dipende da come lo fanno."]).replace("{tema}", tema)
    obiezione = ""
    for t in a.temi:
        if t in p.get("obiezioni", {}):
            obiezione = " " + p["obiezioni"][t].strip("«»")
            break
    if chiave != "positiva" and not obiezione and "generale" in p.get("obiezioni", {}):
        obiezione = " " + p["obiezioni"]["generale"].strip("«»")
    frase = frase[:1].lower() + frase[1:] if apertura.endswith(",") else frase
    if obiezione and not obiezione.rstrip().endswith((".", "?", "!")):
        obiezione = obiezione.rstrip() + "."
    return f"{apertura} {frase}{obiezione}"


def rispondi(mondo: dict, persona_id: str, storia: list[dict], domanda: str, contesto_messaggio: str | None = None, usa_llm: bool = True) -> dict:
    p = next(x for x in mondo["personas"] if x["id"] == persona_id)
    if usa_llm and llm.disponibile():
        sistema = llm.scheda_persona(p, mondo.get("contesto", "")) + (
            "Rispondi come questa persona, in italiano, in prima persona, con frasi brevi (max 80 parole). "
            "Non dire mai di essere un'intelligenza artificiale a meno che te lo chiedano; se te lo chiedono, "
            "spiega che sei un profilo simulato costruito da dati aggregati."
        )
        if contesto_messaggio:
            sistema += f"\nHai appena ricevuto questo messaggio: «{contesto_messaggio}»."
        messaggi = [m for m in storia[-10:] if m.get("role") in {"user", "assistant"}] + [{"role": "user", "content": domanda}]
        try:
            return {"risposta": llm.completa(sistema, messaggi, max_tokens=300).strip(), "modalita": "modello linguistico"}
        except Exception as e:
            return {"risposta": risposta_regole(mondo, p, domanda, contesto_messaggio, len(storia)), "modalita": "regole", "errore_llm": str(e)[:200]}
    return {"risposta": risposta_regole(mondo, p, domanda, contesto_messaggio, len(storia)), "modalita": "regole (dimostrativa)"}
