"""SPECCHIO · API, accesso protetto e server dell'interfaccia."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm, settings
from .analyzer import analizza
from .chat import rispondi
from .engine import Richiesta, simula
from .importer import anteprima, crea_mondo
from .world import (carica_mondo, elenco_mondi, elimina_mondo_utente, origine, salva_mondo_utente, valida_mondo)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
COOKIE = "specchio_sessione"

app = FastAPI(title="SPECCHIO · simulatore di personas di opinione", version="0.2.0")

# ---------------------------------------------------------------- accesso
LIBERI = {"/login", "/api/login", "/api/logout", "/salute", "/static/style.css", "/static/login.js"}
_tentativi: dict[str, list[float]] = {}


def ruolo_richiesta(request: Request) -> str | None:
    if not settings.protezione_attiva():
        return "admin"  # uso locale senza password
    return settings.leggi_sessione(request.cookies.get(COOKIE))


@app.middleware("http")
async def protezione(request: Request, call_next):
    path = request.url.path
    if path in LIBERI or path.startswith("/static/vendor/"):
        return await call_next(request)
    ruolo = ruolo_richiesta(request)
    serve_admin = path.startswith("/admin") or path.startswith("/api/admin") or path.startswith("/static/admin")
    if ruolo is None or (serve_admin and ruolo != "admin"):
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Accesso richiesto"}, status_code=401)
        area = "admin" if serve_admin else "utente"
        return RedirectResponse(f"/login?area={area}&torna={path}", status_code=303)
    request.state.ruolo = ruolo
    return await call_next(request)


class LoginIn(BaseModel):
    password: str = Field(max_length=200)
    area: str = "utente"


@app.post("/api/login")
def api_login(body: LoginIn, request: Request):
    ip = request.client.host if request.client else "?"
    ora = time.time()
    recenti = [t for t in _tentativi.get(ip, []) if ora - t < 300]
    if len(recenti) >= 8:
        raise HTTPException(429, "Troppi tentativi: riprova tra qualche minuto")
    ruolo = "admin" if body.area == "admin" else "utente"
    ok = settings.verifica_password(ruolo, body.password) or (ruolo == "utente" and settings.verifica_password("admin", body.password))
    if not ok:
        _tentativi[ip] = recenti + [ora]
        raise HTTPException(401, "Password non corretta")
    if ruolo == "utente" and settings.verifica_password("admin", body.password):
        ruolo = "admin"
    risposta = JSONResponse({"ok": True, "ruolo": ruolo})
    https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    risposta.set_cookie(COOKIE, settings.crea_sessione(ruolo), httponly=True, samesite="lax", secure=https, max_age=12 * 3600)
    return risposta


@app.post("/api/logout")
def api_logout():
    r = JSONResponse({"ok": True})
    r.delete_cookie(COOKIE)
    return r


@app.get("/salute")
def salute():
    return {"ok": True}


# ---------------------------------------------------------------- area pubblica
class SimulaIn(BaseModel):
    mondo_id: str
    messaggio: str = Field(min_length=3, max_length=4000)
    canale: str
    unita_bersaglio: list[str] | None = None
    composizione: dict[str, dict[str, int]] | None = None
    round: int = Field(8, ge=1, le=20)
    esecuzioni: int = Field(3, ge=1, le=10)
    seme: int = 7
    usa_llm: bool = False


class ChatIn(BaseModel):
    mondo_id: str
    persona_id: str
    domanda: str = Field(min_length=1, max_length=2000)
    storia: list[dict] = []
    contesto_messaggio: str | None = None
    usa_llm: bool = True


class ImportaIn(BaseModel):
    csv: str
    nome: str = "Mondo da file"
    colonna_gruppo: str | None = None
    colonne_clima: list[str] = []
    colonna_fiducia: str | None = None
    modello_id: str = "aaa-interno"


def _mondo_visibile(mondo_id: str, request: Request) -> dict:
    try:
        m = carica_mondo(mondo_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if mondo_id in settings.carica()["mondi_nascosti"] and getattr(request.state, "ruolo", None) != "admin":
        raise HTTPException(404, "Mondo non disponibile")
    return m


@app.get("/api/stato")
def stato(request: Request):
    s = settings.carica()["simulazione"]
    return {"modello_linguistico": llm.provider(), "disponibile": llm.disponibile(), "ruolo": request.state.ruolo,
            "protezione": settings.protezione_attiva(), "round": s["round"], "esecuzioni": s["esecuzioni"]}


@app.get("/api/mondi")
def mondi(request: Request):
    nascosti = set(settings.carica()["mondi_nascosti"])
    return [{"id": m["id"], "nome": m["nome"], "tipo": m["tipo"], "descrizione": m.get("descrizione", "")}
            for m in elenco_mondi().values() if m["id"] not in nascosti]


@app.get("/api/mondi/{mondo_id}")
def mondo(mondo_id: str, request: Request):
    return _mondo_visibile(mondo_id, request)


@app.post("/api/analizza")
def api_analizza(body: dict):
    return analizza(str(body.get("messaggio", ""))[:4000]).to_dict()


@app.post("/api/simula")
def api_simula(body: SimulaIn, request: Request):
    m = _mondo_visibile(body.mondo_id, request)
    if body.canale not in {c["id"] for c in m["canali"]}:
        raise HTTPException(400, "Canale non valido per questo mondo")
    settings.conta("simulazioni")
    return simula(Richiesta(mondo=m, messaggio=body.messaggio, canale=body.canale, unita_bersaglio=body.unita_bersaglio,
                            composizione=body.composizione, round=body.round, esecuzioni=body.esecuzioni,
                            seme=body.seme, usa_llm=body.usa_llm))


@app.post("/api/chat")
def api_chat(body: ChatIn, request: Request):
    m = _mondo_visibile(body.mondo_id, request)
    if body.persona_id not in {p["id"] for p in m["personas"]}:
        raise HTTPException(404, "Persona non trovata")
    settings.conta("dialoghi")
    return rispondi(m, body.persona_id, body.storia, body.domanda, body.contesto_messaggio, body.usa_llm)


@app.post("/api/importa/anteprima")
def api_anteprima(body: ImportaIn):
    return anteprima(body.csv)


@app.post("/api/importa")
def api_importa(body: ImportaIn, request: Request):
    if not body.colonna_gruppo:
        raise HTTPException(400, "Scegli la colonna che indica il gruppo o la categoria")
    modello = _mondo_visibile(body.modello_id, request)
    m = crea_mondo(body.csv, body.nome, body.colonna_gruppo, body.colonne_clima, body.colonna_fiducia, modello)
    if not m["personas"]:
        raise HTTPException(400, "Nessun gruppo ha almeno 10 risposte: non è possibile creare personas rispettando l'anonimato")
    salva_mondo_utente(m)
    settings.conta("importazioni")
    return {"id": m["id"], "personas": len(m["personas"])}


# ---------------------------------------------------------------- area riservata
def _maschera(k: str) -> str:
    return ("impostata · ••••" + k[-4:]) if k else ""


@app.get("/api/admin/impostazioni")
def admin_get():
    d = settings.carica()
    l = d["llm"]
    return {
        "llm": {**{k: v for k, v in l.items() if not k.endswith("_key")},
                "anthropic_key": _maschera(l.get("anthropic_key", "")), "openai_key": _maschera(l.get("openai_key", "")),
                "attivo": llm.provider()},
        "simulazione": d["simulazione"],
        "statistiche": d["statistiche"],
        "password_personalizzate": sorted(d["password"].keys()),
        "mondi": [{"id": m["id"], "nome": m["nome"], "tipo": m["tipo"], "personas": len(m["personas"]),
                   "origine": origine(m["id"]), "visibile": m["id"] not in d["mondi_nascosti"]} for m in elenco_mondi().values()],
    }


class LlmIn(BaseModel):
    provider: str = ""
    anthropic_model: str = ""
    openai_model: str = ""
    openai_base_url: str = ""
    anthropic_key: str | None = None  # None = non cambiare, "" = cancella
    openai_key: str | None = None


@app.post("/api/admin/llm")
def admin_llm(body: LlmIn):
    if body.provider not in {"", "mock", "anthropic", "openai"}:
        raise HTTPException(400, "Fornitore non valido")

    def f(d):
        l = d["llm"]
        l.update({"provider": body.provider, "anthropic_model": body.anthropic_model.strip() or l["anthropic_model"],
                  "openai_model": body.openai_model.strip() or l["openai_model"],
                  "openai_base_url": body.openai_base_url.strip() or l["openai_base_url"]})
        for k in ["anthropic_key", "openai_key"]:
            v = getattr(body, k)
            if v is not None:
                l[k] = v.strip()
    settings.aggiorna(f)
    return {"ok": True, "attivo": llm.provider()}


@app.post("/api/admin/llm/prova")
def admin_llm_prova():
    if not llm.disponibile():
        raise HTTPException(400, "Nessun modello configurato: inserisci una chiave e salva")
    try:
        t = time.time()
        r = llm.completa("Rispondi solo con la parola OK.", [{"role": "user", "content": "Prova di collegamento"}], max_tokens=10, temperatura=0)
        return {"ok": True, "risposta": r.strip()[:50], "secondi": round(time.time() - t, 1), "fornitore": llm.provider()}
    except Exception as e:
        raise HTTPException(502, f"Il modello non risponde: {str(e)[:200]}")


class SimParIn(BaseModel):
    round: int = Field(ge=1, le=20)
    esecuzioni: int = Field(ge=1, le=10)
    max_agenti: int = Field(ge=50, le=2000)


@app.post("/api/admin/simulazione")
def admin_sim(body: SimParIn):
    settings.aggiorna(lambda d: d["simulazione"].update(body.model_dump()))
    return {"ok": True}


class VisIn(BaseModel):
    visibile: bool


@app.post("/api/admin/mondi/{mondo_id}/visibile")
def admin_visibile(mondo_id: str, body: VisIn):
    def f(d):
        s = set(d["mondi_nascosti"])
        (s.discard if body.visibile else s.add)(mondo_id)
        d["mondi_nascosti"] = sorted(s)
    settings.aggiorna(f)
    return {"ok": True}


@app.get("/api/admin/mondi/{mondo_id}")
def admin_mondo(mondo_id: str):
    try:
        return carica_mondo(mondo_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.put("/api/admin/mondi/{mondo_id}")
def admin_salva_mondo(mondo_id: str, mondo: dict):
    if mondo.get("id") != mondo_id:
        raise HTTPException(400, "L'id nel testo deve essere uguale a quello del mondo")
    errori = valida_mondo(mondo)
    if errori:
        raise HTTPException(400, "; ".join(errori[:6]))
    salva_mondo_utente(mondo)
    return {"ok": True}


@app.post("/api/admin/mondi")
def admin_nuovo_mondo(mondo: dict):
    errori = valida_mondo(mondo)
    if errori:
        raise HTTPException(400, "; ".join(errori[:6]))
    salva_mondo_utente(mondo)
    return {"ok": True, "id": mondo["id"]}


@app.delete("/api/admin/mondi/{mondo_id}")
def admin_elimina_mondo(mondo_id: str):
    if not elimina_mondo_utente(mondo_id):
        raise HTTPException(400, "I mondi predefiniti non si eliminano: puoi nasconderli")
    return {"ok": True, "origine_ora": origine(mondo_id) if mondo_id in elenco_mondi() else None}


class PwIn(BaseModel):
    ruolo: str
    nuova: str = Field(min_length=8, max_length=200)


@app.post("/api/admin/password")
def admin_password(body: PwIn):
    if body.ruolo not in {"utente", "admin"}:
        raise HTTPException(400, "Ruolo non valido")
    settings.imposta_password(body.ruolo, body.nuova)
    return {"ok": True}


# ---------------------------------------------------------------- pagine
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND / "index.html")

    @app.get("/login")
    def login_page():
        return FileResponse(FRONTEND / "login.html")

    @app.get("/admin")
    def admin_page():
        return FileResponse(FRONTEND / "admin.html")
