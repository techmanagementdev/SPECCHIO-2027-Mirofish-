"""Collegamento opzionale a un modello linguistico.

Configurazione: area riservata (/admin) oppure variabili d'ambiente:
  LLM_PROVIDER   anthropic | openai | mock (predefinito: mock se non ci sono chiavi)
  ANTHROPIC_API_KEY, ANTHROPIC_MODEL (predefinito claude-haiku-5-5)
  OPENAI_API_KEY, OPENAI_BASE_URL (qualsiasi API compatibile OpenAI), OPENAI_MODEL

Senza chiavi il sistema funziona in modalità dimostrativa con regole e frasi tipo.
"""
from __future__ import annotations

import json
import os
import re

import httpx


def _cfg() -> dict:
    """Impostazioni dell'area riservata, con le variabili d'ambiente come riserva."""
    from .settings import carica
    c = carica()["llm"]
    return {
        "provider": (c.get("provider") or os.getenv("LLM_PROVIDER", "")).lower(),
        "anthropic_key": c.get("anthropic_key") or os.getenv("ANTHROPIC_API_KEY", ""),
        "anthropic_model": c.get("anthropic_model") or os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        "openai_key": c.get("openai_key") or os.getenv("OPENAI_API_KEY", ""),
        "openai_model": c.get("openai_model") or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "openai_base_url": c.get("openai_base_url") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    }


def provider() -> str:
    c = _cfg()
    p = c["provider"]
    if p == "mock":
        return "mock"
    if p == "anthropic" and c["anthropic_key"]:
        return "anthropic"
    if p == "openai" and c["openai_key"]:
        return "openai"
    if not p:
        if c["anthropic_key"]:
            return "anthropic"
        if c["openai_key"]:
            return "openai"
    return "mock"


def disponibile() -> bool:
    return provider() != "mock"


def completa(sistema: str, messaggi: list[dict], max_tokens: int = 600, temperatura: float = 0.8) -> str:
    p, c = provider(), _cfg()
    if p == "anthropic":
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": c["anthropic_key"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": c["anthropic_model"], "max_tokens": max_tokens, "temperature": temperatura,
                  "system": sistema, "messages": messaggi},
            timeout=60,
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"])
    if p == "openai":
        base = c["openai_base_url"].rstrip("/")
        r = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {c['openai_key']}"},
            json={"model": c["openai_model"], "max_tokens": max_tokens, "temperature": temperatura,
                  "messages": [{"role": "system", "content": sistema}] + messaggi},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    raise RuntimeError("Nessun modello configurato")


def estrai_json(testo: str) -> dict:
    m = re.search(r"\{.*\}", testo, re.S)
    if not m:
        raise ValueError("Risposta senza JSON")
    return json.loads(m.group(0))


def scheda_persona(p: dict, contesto: str) -> str:
    canali = ", ".join(f"{k} ({round(v * 100)}%)" for k, v in sorted(p.get("canali", {}).items(), key=lambda x: -x[1]))
    return (
        f"Sei una persona di opinione sintetica, costruita da dati aggregati: non sei una persona reale.\n"
        f"Contesto: {contesto}\n"
        f"Profilo: {p['nome']} ({p.get('categoria', '')}). {p.get('descrizione', '')}\n"
        f"Atteggiamento di partenza (da -1 a 1): {p['atteggiamento']}. Fiducia nel mittente (0-1): {p['fiducia']}. "
        f"Scetticismo (0-1): {p['scetticismo']}.\n"
        f"Criticità che senti: {'; '.join(p.get('criticita', []))}.\n"
        f"Aspettative: {'; '.join(p.get('aspettative', []))}.\n"
        f"Canali di cui ti fidi: {canali}.\n"
        f"Modo di parlare: {p.get('voce', 'diretto e concreto')}.\n"
    )


def reazione_persona(p: dict, contesto: str, messaggio: str, canale_nome: str) -> dict:
    sistema = scheda_persona(p, contesto) + (
        "Rispondi solo con un oggetto JSON con le chiavi: "
        '"punteggio" (intero da -100 a 100, gradimento del messaggio), "emozione" (una parola), '
        '"frase" (cosa diresti a un collega o a un vicino, max 30 parole, in italiano, con la tua voce), '
        '"obiezione" (la tua obiezione principale, max 15 parole), "condivisione" (da 0 a 1, quanto ne parleresti ad altri).'
    )
    testo = completa(sistema, [{"role": "user", "content": f"Ricevi questo messaggio tramite {canale_nome}:\n\n{messaggio}"}], max_tokens=300)
    d = estrai_json(testo)
    return {
        "punteggio": max(-100, min(100, int(d.get("punteggio", 0)))),
        "emozione": str(d.get("emozione", ""))[:30],
        "frase": str(d.get("frase", ""))[:300],
        "obiezione": str(d.get("obiezione", ""))[:160],
        "condivisione": max(0.0, min(1.0, float(d.get("condivisione", 0.5)))),
    }
