"""Impostazioni modificabili dall'area riservata, accesso e statistiche d'uso.

Tutto è salvato in DATA_DIR (predefinito: cartella data/ del repository; su Railway un volume).
Le password non sono mai salvate in chiaro: solo hash PBKDF2.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR") or Path(__file__).resolve().parents[2] / "data")
FILE = DATA_DIR / "impostazioni.json"
_lock = threading.Lock()

PREDEFINITE = {
    "llm": {"provider": "", "anthropic_model": "claude-haiku-5-5", "openai_model": "gpt-4o-mini",
            "openai_base_url": "https://api.openai.com/v1", "anthropic_key": "", "openai_key": ""},
    "simulazione": {"round": 8, "esecuzioni": 3, "max_agenti": 400},
    "mondi_nascosti": [],
    "password": {},  # ruolo -> hash
    "statistiche": {"simulazioni": 0, "dialoghi": 0, "importazioni": 0, "ultimo_uso": None},
}


def carica() -> dict:
    with _lock:
        dati = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    out = json.loads(json.dumps(PREDEFINITE))
    for k, v in dati.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def salva(dati: dict) -> None:
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(FILE)


def aggiorna(fn) -> dict:
    dati = carica()
    fn(dati)
    salva(dati)
    return dati


def conta(voce: str) -> None:
    def f(d):
        d["statistiche"][voce] = d["statistiche"].get(voce, 0) + 1
        d["statistiche"]["ultimo_uso"] = time.strftime("%Y-%m-%d %H:%M")
    try:
        aggiorna(f)
    except OSError:
        pass


# ---------- password ----------
def _hash(pw: str, sale: bytes | None = None) -> str:
    sale = sale or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), sale, 200_000)
    return base64.b64encode(sale).decode() + "$" + base64.b64encode(h).decode()


def _verifica_hash(pw: str, salvato: str) -> bool:
    sale_b64, h_b64 = salvato.split("$", 1)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), base64.b64decode(sale_b64), 200_000)
    return hmac.compare_digest(base64.b64encode(h).decode(), h_b64)


def protezione_attiva() -> bool:
    d = carica()
    return bool(d["password"] or os.getenv("ACCESS_PASSWORD") or os.getenv("ADMIN_PASSWORD"))


def verifica_password(ruolo: str, pw: str) -> bool:
    d = carica()
    if ruolo in d["password"]:
        return _verifica_hash(pw, d["password"][ruolo])
    env = os.getenv("ADMIN_PASSWORD" if ruolo == "admin" else "ACCESS_PASSWORD") or (os.getenv("ACCESS_PASSWORD") if ruolo == "admin" else None)
    return bool(env) and hmac.compare_digest(pw.encode(), env.encode())


def imposta_password(ruolo: str, pw: str) -> None:
    aggiorna(lambda d: d["password"].__setitem__(ruolo, _hash(pw)))


# ---------- sessioni firmate ----------
def _segreto() -> bytes:
    env = os.getenv("SECRET_KEY")
    if env:
        return env.encode()
    f = DATA_DIR / ".segreto"
    if not f.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip().encode()


def crea_sessione(ruolo: str, durata_ore: int = 12) -> str:
    corpo = base64.urlsafe_b64encode(json.dumps({"r": ruolo, "e": int(time.time()) + durata_ore * 3600}).encode()).decode()
    firma = hmac.new(_segreto(), corpo.encode(), hashlib.sha256).hexdigest()
    return corpo + "." + firma


def leggi_sessione(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    corpo, firma = token.rsplit(".", 1)
    if not hmac.compare_digest(hmac.new(_segreto(), corpo.encode(), hashlib.sha256).hexdigest(), firma):
        return None
    try:
        d = json.loads(base64.urlsafe_b64decode(corpo.encode()))
    except ValueError:
        return None
    return d["r"] if d.get("e", 0) > time.time() else None
