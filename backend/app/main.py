"""SPECCHIO · API e server dell'interfaccia."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm
from .analyzer import analizza
from .chat import rispondi
from .engine import Richiesta, simula
from .importer import anteprima, crea_mondo
from .world import carica_mondo, elenco_mondi, salva_mondo_utente

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(title="SPECCHIO · simulatore di personas di opinione", version="0.1.0")


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


@app.get("/api/stato")
def stato():
    return {"modello_linguistico": llm.provider(), "disponibile": llm.disponibile()}


@app.get("/api/mondi")
def mondi():
    return [{"id": m["id"], "nome": m["nome"], "tipo": m["tipo"], "descrizione": m.get("descrizione", "")} for m in elenco_mondi().values()]


@app.get("/api/mondi/{mondo_id}")
def mondo(mondo_id: str):
    try:
        return carica_mondo(mondo_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.post("/api/analizza")
def api_analizza(body: dict):
    return analizza(body.get("messaggio", "")).to_dict()


@app.post("/api/simula")
def api_simula(body: SimulaIn):
    try:
        m = carica_mondo(body.mondo_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if body.canale not in {c["id"] for c in m["canali"]}:
        raise HTTPException(400, "Canale non valido per questo mondo")
    return simula(Richiesta(mondo=m, messaggio=body.messaggio, canale=body.canale, unita_bersaglio=body.unita_bersaglio,
                            composizione=body.composizione, round=body.round, esecuzioni=body.esecuzioni,
                            seme=body.seme, usa_llm=body.usa_llm))


@app.post("/api/chat")
def api_chat(body: ChatIn):
    try:
        m = carica_mondo(body.mondo_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if body.persona_id not in {p["id"] for p in m["personas"]}:
        raise HTTPException(404, "Persona non trovata")
    return rispondi(m, body.persona_id, body.storia, body.domanda, body.contesto_messaggio, body.usa_llm)


@app.post("/api/importa/anteprima")
def api_anteprima(body: ImportaIn):
    return anteprima(body.csv)


@app.post("/api/importa")
def api_importa(body: ImportaIn):
    if not body.colonna_gruppo:
        raise HTTPException(400, "Scegli la colonna che indica il gruppo o la categoria")
    try:
        modello = carica_mondo(body.modello_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    m = crea_mondo(body.csv, body.nome, body.colonna_gruppo, body.colonne_clima, body.colonna_fiducia, modello)
    if not m["personas"]:
        raise HTTPException(400, "Nessun gruppo ha almeno 10 risposte: non è possibile creare personas rispettando l'anonimato")
    salva_mondo_utente(m)
    return {"id": m["id"], "personas": len(m["personas"])}


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND / "index.html")
