"""Collegamento a LimeSurvey tramite l'interfaccia RemoteControl 2 (JSON-RPC).

Prerequisito su LimeSurvey: Configurazione → Impostazioni globali → Interfacce →
«Interfaccia RPC attiva» = JSON-RPC.

Le risposte scaricate restano solo in memoria per pochi minuti e servono a calcolare le
medie per gruppo: non vengono mai salvate su disco.
"""
from __future__ import annotations

import base64
import os
import re
import time

import httpx

PERCORSI = ["/index.php/admin/remotecontrol", "/admin/remotecontrol", "/index.php?r=admin/remotecontrol"]
_cache: dict[str, tuple[float, str, dict]] = {}  # sid -> (ora, csv, etichette)
DURATA_CACHE = 600


class ErroreLimeSurvey(Exception):
    pass


def configurazione() -> dict:
    from .settings import carica
    c = carica().get("limesurvey", {})
    return {
        "url": (c.get("url") or os.getenv("LIMESURVEY_URL", "")).strip(),
        "utente": (c.get("utente") or os.getenv("LIMESURVEY_USER", "")).strip(),
        "password": c.get("password") or os.getenv("LIMESURVEY_PASSWORD", ""),
    }


def configurato() -> bool:
    c = configurazione()
    return bool(c["url"] and c["utente"] and c["password"])


def _candidati(url: str) -> list[str]:
    url = url.rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    if "remotecontrol" in url:
        return [url]
    base = re.sub(r"/index\.php.*$|/admin.*$", "", url)
    return [base + p for p in PERCORSI]


class Client:
    def __init__(self, url: str, utente: str, password: str, transport: httpx.BaseTransport | None = None):
        self.utente, self.password = utente, password
        self.http = httpx.Client(timeout=60, transport=transport, follow_redirects=True)
        self.endpoint = None
        self.chiave = None
        self._url = url

    def _rpc(self, endpoint: str, metodo: str, params: list):
        r = self.http.post(endpoint, json={"method": metodo, "params": params, "id": 1}, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        d = r.json()
        if d.get("error"):
            raise ErroreLimeSurvey(str(d["error"]))
        return d.get("result")

    def __enter__(self):
        ultimo = None
        for ep in _candidati(self._url):
            try:
                ris = self._rpc(ep, "get_session_key", [self.utente, self.password])
            except (httpx.HTTPError, ValueError) as e:
                ultimo = e
                continue
            if isinstance(ris, dict):
                stato = ris.get("status", "errore")
                if "invalid" in stato.lower():
                    raise ErroreLimeSurvey("Nome utente o password di LimeSurvey non corretti")
                raise ErroreLimeSurvey(f"LimeSurvey ha risposto: {stato}")
            if isinstance(ris, str) and ris:
                self.endpoint, self.chiave = ep, ris
                return self
        raise ErroreLimeSurvey("Interfaccia RemoteControl non raggiungibile: controlla l'indirizzo e che JSON-RPC sia attivo "
                               f"nelle impostazioni globali di LimeSurvey ({type(ultimo).__name__ if ultimo else 'nessuna risposta'})")

    def __exit__(self, *a):
        try:
            if self.chiave:
                self._rpc(self.endpoint, "release_session_key", [self.chiave])
        except Exception:
            pass
        self.http.close()

    def chiama(self, metodo: str, *params):
        return self._rpc(self.endpoint, metodo, [self.chiave, *params])

    def sondaggi(self) -> list[dict]:
        ris = self.chiama("list_surveys", self.utente)
        if isinstance(ris, dict):  # {"status": "No surveys found"}
            return []
        out = []
        for s in ris:
            sid = str(s.get("sid"))
            out.append({"sid": sid, "titolo": s.get("surveyls_title") or sid, "attivo": s.get("active") == "Y",
                        "scadenza": s.get("expires")})
        for s in out:
            try:
                rias = self.chiama("get_summary", s["sid"], "all")
                s["completate"] = int(rias.get("completed_responses", 0)) if isinstance(rias, dict) else None
            except Exception:
                s["completate"] = None
        return out

    def etichette(self, sid: str) -> dict[str, str]:
        """Codice della domanda -> testo, per mostrare domande leggibili."""
        ris = self.chiama("list_questions", sid)
        out = {}
        if isinstance(ris, list):
            for q in ris:
                testo = re.sub(r"<[^>]+>", " ", q.get("question") or "")
                out[q.get("title", "")] = re.sub(r"\s+", " ", testo).strip()[:160]
        return out

    def opzioni(self, sid: str, colonna: str) -> dict[str, str]:
        """Codice -> testo delle risposte di una domanda a scelta singola (es. A1 -> «Operativi su strada»)."""
        base = colonna.split("[")[0]
        ris = self.chiama("list_questions", sid)
        qid = next((q.get("qid") for q in (ris if isinstance(ris, list) else []) if q.get("title") == base), None)
        if not qid:
            return {}
        p = self.chiama("get_question_properties", qid, ["answeroptions"])
        ao = p.get("answeroptions") if isinstance(p, dict) else None
        if not isinstance(ao, dict):
            return {}
        return {k: re.sub(r"<[^>]+>", "", (v or {}).get("answer", "")).strip() for k, v in ao.items()}

    def risposte_csv(self, sid: str) -> str:
        ris = self.chiama("export_responses", sid, "csv", None, "complete", "code", "short")
        if isinstance(ris, dict):
            stato = ris.get("status", "")
            if "no response" in stato.lower() or "no data" in stato.lower():
                raise ErroreLimeSurvey("Il sondaggio non ha ancora risposte complete")
            raise ErroreLimeSurvey(f"Esportazione non riuscita: {stato}")
        testo = base64.b64decode(ris).decode("utf-8-sig", errors="replace")
        return testo


def _client(transport=None) -> Client:
    c = configurazione()
    if not (c["url"] and c["utente"] and c["password"]):
        raise ErroreLimeSurvey("Collegamento a LimeSurvey non configurato: inserisci indirizzo, utente e password nell'area riservata")
    return Client(c["url"], c["utente"], c["password"], transport)


def prova(transport=None) -> dict:
    with _client(transport) as cl:
        s = cl.sondaggi()
        return {"ok": True, "sondaggi": len(s), "endpoint": cl.endpoint}


def elenco(transport=None) -> list[dict]:
    with _client(transport) as cl:
        return cl.sondaggi()


def scarica(sid: str, transport=None, forza: bool = False) -> tuple[str, dict]:
    sid = re.sub(r"\D", "", sid)
    ora = time.time()
    for k in [k for k, v in _cache.items() if ora - v[0] > DURATA_CACHE]:
        del _cache[k]
    if not forza and sid in _cache:
        return _cache[sid][1], _cache[sid][2]
    with _client(transport) as cl:
        csv_testo = cl.risposte_csv(sid)
        try:
            et = cl.etichette(sid)
        except Exception:
            et = {}
    _cache[sid] = (ora, csv_testo, et)
    return csv_testo, et


def etichetta_colonna(col: str, etichette: dict) -> str:
    """Le colonne esportate sono del tipo CODICE o CODICE[SQ001]: si cerca il testo della domanda."""
    base = col.split("[")[0]
    return etichette.get(col) or etichette.get(base) or ""


def opzioni(sid: str, colonna: str, transport=None) -> dict[str, str]:
    try:
        with _client(transport) as cl:
            return cl.opzioni(re.sub(r"\D", "", sid), colonna)
    except Exception:
        return {}


def opzioni_multiple(sid: str, colonne: list[str], transport=None) -> dict[str, dict[str, str]]:
    out = {}
    try:
        with _client(transport) as cl:
            for c in colonne[:40]:
                try:
                    o = cl.opzioni(re.sub(r"\D", "", sid), c)
                    if o:
                        out[c] = o
                except Exception:
                    continue
    except Exception:
        pass
    return out
