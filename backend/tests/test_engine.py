"""Test di base del motore. Avvio: cd backend && python -m pytest"""
from fastapi.testclient import TestClient

from app import llm
from app.analyzer import analizza
from app.engine import Richiesta, simula
from app.importer import crea_mondo
from app.main import app
from app.world import carica_mondo, elenco_mondi

client = TestClient(app)


def test_preset_caricati():
    mondi = elenco_mondi()
    for mid in ["aaa-interno", "aaa-territorio", "citta-esempio"]:
        m = mondi[mid]
        ids = {p["id"] for p in m["personas"]}
        for mix in m["composizione"].values():
            assert set(mix) <= ids
        for e in m["esempi"]:
            assert e["canale"] in {c["id"] for c in m["canali"]}


def test_analisi_verso():
    assert analizza("Dal 2027 la tassa sui rifiuti aumenterà del 6%.").temi["tariffe"] < 0
    assert analizza("I pedaggi resteranno fermi fino al 2029.").temi["tariffe"] > 0
    assert analizza("Nuova linea di autobus gratuita anche la sera.").temi["trasporti"] > 0
    assert "tariffe" not in analizza("Un parco di 4 ettari con 300 alberi.").temi


def test_simulazione_ripetibile_e_coerente():
    m = carica_mondo("citta-esempio")
    buono = simula(Richiesta(mondo=m, messaggio="Da settembre una nuova linea di autobus collegherà la periferia e il centro ogni 30 minuti, gratuita per gli under 26.", canale="gruppi"))
    cattivo = simula(Richiesta(mondo=m, messaggio="Dal 2027 la tassa sui rifiuti aumenterà del 6%.", canale="social"))
    assert buono["finale"]["indice"] > cattivo["finale"]["indice"] + 20
    ripetuto = simula(Richiesta(mondo=m, messaggio="Dal 2027 la tassa sui rifiuti aumenterà del 6%.", canale="social"))
    assert ripetuto["finale"] == cattivo["finale"]
    assert len(cattivo["serie"]["indice"]["media"]) == 9
    assert 1 <= cattivo["stelle"] <= 3


def test_versione_con_ascolto_migliore():
    m = carica_mondo("aaa-interno")
    a, b = m["esempi"][0], m["esempi"][1]
    ra = simula(Richiesta(mondo=m, messaggio=a["testo"], canale=a["canale"]))
    rb = simula(Richiesta(mondo=m, messaggio=b["testo"], canale=b["canale"]))
    assert rb["finale"]["indice"] > ra["finale"]["indice"]


def test_llm_simulato(monkeypatch):
    """Con un modello configurato le reazioni arrivano dal modello (qui sostituito da una funzione finta)."""
    monkeypatch.setattr(llm, "disponibile", lambda: True)
    monkeypatch.setattr(llm, "reazione_persona", lambda p, c, msg, can: {"punteggio": -80, "emozione": "rabbia", "frase": "Non ci sto.", "obiezione": "Troppo poco", "condivisione": 0.9})
    m = carica_mondo("citta-esempio")
    r = simula(Richiesta(mondo=m, messaggio="Nuovo parco con 300 alberi.", canale="social", usa_llm=True))
    assert r["modalita"] == "modello linguistico"
    assert r["finale"]["indice"] < 40
    assert any("Troppo poco" in o["testo"] for o in r["obiezioni"])


def test_import_rispetta_soglia_anonimato():
    righe = ["categoria;Q1;Q2"] + [f"Operai;{2 + i % 2};{3}" for i in range(15)] + [f"Impiegati;4;5" for _ in range(12)] + ["Dirigenti;5;5"] * 3
    m = crea_mondo("\n".join(righe), "Prova", "categoria", ["Q1", "Q2"], None, carica_mondo("aaa-interno"))
    nomi = {p["nome"] for p in m["personas"]}
    assert nomi == {"Operai", "Impiegati"}  # i 3 dirigenti non bastano per un gruppo né per «Altri»
    operai = next(p for p in m["personas"] if p["nome"] == "Operai")
    impiegati = next(p for p in m["personas"] if p["nome"] == "Impiegati")
    assert impiegati["atteggiamento"] > operai["atteggiamento"]


def test_api():
    assert client.get("/api/stato").status_code == 200
    r = client.post("/api/simula", json={"mondo_id": "aaa-territorio", "messaggio": "Chiusure notturne annunciate con 24 ore di anticipo.", "canale": "app_traffico", "esecuzioni": 2, "round": 4})
    assert r.status_code == 200 and len(r.json()["unita"]) == 5
    assert client.post("/api/simula", json={"mondo_id": "aaa-territorio", "messaggio": "Prova", "canale": "inesistente"}).status_code == 400
    c = client.post("/api/chat", json={"mondo_id": "aaa-interno", "persona_id": "caposquadra", "domanda": "Qual è il problema principale?", "usa_llm": False})
    assert c.status_code == 200 and "squadre ridotte" in c.json()["risposta"]
