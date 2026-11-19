"""Area cliente: report, accesso con codice e impact simulation."""
from pathlib import Path

from fastapi.testclient import TestClient

from app import settings
from app.main import app

CSV = (Path(__file__).resolve().parents[2] / "docs" / "esempio_limesurvey.csv").read_text()


def test_area_cliente(monkeypatch):
    monkeypatch.setenv("ACCESS_PASSWORD", "team-prova-1")
    team = TestClient(app)
    team.post("/api/login", json={"password": "team-prova-1", "area": "utente"})
    r = team.post("/api/report", json={"fonte": "file", "csv": CSV, "titolo": "Clima interno prova", "cliente": "Cliente X",
                                       "colonna_gruppo": "categoria", "colonne_clima": ["Q01_orgoglio", "Q02_consiglierei", "Q03_sicurezza"],
                                       "colonna_fiducia": "Q04_fiducia_direzione", "codice": "codice-cliente-1"})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert any(x["id"] == rid for x in team.get("/api/report").json())

    cliente = TestClient(app)
    assert cliente.get(f"/r/{rid}").status_code == 200  # la pagina si apre e chiede il codice
    assert cliente.get(f"/api/r/{rid}").status_code == 401
    assert cliente.get("/api/mondi").status_code == 401  # il cliente non entra nel simulatore interno
    assert cliente.post(f"/api/r/{rid}/login", json={"codice": "sbagliato!"}).status_code == 401
    assert cliente.post(f"/api/r/{rid}/login", json={"codice": "codice-cliente-1"}).status_code == 200
    d = cliente.get(f"/api/r/{rid}").json()
    rep, mondo = d["report"], d["mondo"]
    assert "codice_hash" not in rep
    assert rep["risposte"] == 304 and 0 < rep["indice"] < 100
    assert {g["nome"] for g in rep["gruppi"]} >= {"Operativi su strada", "Dirigenti e quadri"}
    assert all(g["n"] >= 10 for g in rep["gruppi"])
    assert rep["in_breve"] and rep["domande"][0]["emoji"] in "🟢🟡🔴"
    strada = next(p for p in mondo["personas"] if p["nome"] == "Operativi su strada")
    assert strada["criticita"]  # arricchite dal report

    sim = cliente.post(f"/api/r/{rid}/simula", json={"messaggio": "Dal 2027 un piano welfare da 600 euro per tutti, presentato in incontri con proposte.", "canale": mondo["canali"][0]["id"]})
    assert sim.status_code == 200 and "finale" in sim.json()
    chat = cliente.post(f"/api/r/{rid}/chat", json={"persona_id": strada["id"], "domanda": "Qual è il problema principale?"})
    assert chat.status_code == 200 and chat.json()["risposta"]

    altro = TestClient(app)
    altro.post(f"/api/r/{rid}/login", json={"codice": "codice-cliente-1"})
    assert altro.get("/api/r/ZZZZZZZZ").status_code == 401  # il codice vale solo per il proprio report
    settings.FILE.unlink(missing_ok=True)
