"""Collegamento a LimeSurvey con un server RemoteControl simulato."""
import base64
import json

import httpx
from fastapi.testclient import TestClient

from app import limesurvey, settings
from app.main import app

RIGHE = ["id,submitdate,G01,Q01,Q02,Q03"]
RIGHE += [f"{i},2027-01-10,A1,{2 + i % 2},2,{2}" for i in range(14)]
RIGHE += [f"{100 + i},2027-01-10,A2,4,5,{4}" for i in range(11)]
RIGHE += [f"{200 + i},2027-01-10,A3,3,3,3" for i in range(4)]
CSV = "\n".join(RIGHE)


def server(request: httpx.Request) -> httpx.Response:
    if not request.url.path.endswith("/index.php/admin/remotecontrol"):
        return httpx.Response(404)
    d = json.loads(request.content)
    m, p = d["method"], d["params"]
    if m == "get_session_key":
        r = "chiave-123" if p == ["luca", "giusta"] else {"status": "Invalid user name or password"}
    elif m == "release_session_key":
        r = "OK"
    elif m == "list_surveys":
        r = [{"sid": 445566, "surveyls_title": "Clima interno 2027", "active": "Y", "expires": None}]
    elif m == "get_summary":
        r = {"completed_responses": "29"}
    elif m == "list_questions":
        r = [{"qid": 7, "title": "G01", "question": "<p>In quale <b>area</b> lavora?</p>"},
             {"qid": 8, "title": "Q01", "question": "Quanto è orgoglioso di lavorare qui?"},
             {"qid": 9, "title": "Q03", "question": "Quanta fiducia ha nella direzione?"}]
    elif m == "get_question_properties":
        r = {"answeroptions": {"A1": {"answer": "Operativi su strada"}, "A2": {"answer": "Uffici"}, "A3": {"answer": "Direzione"}}}
    elif m == "export_responses":
        r = base64.b64encode(CSV.encode()).decode()
    else:
        r = {"status": "metodo sconosciuto"}
    return httpx.Response(200, json={"id": 1, "result": r, "error": None})


T = httpx.MockTransport(server)


def configura(password="giusta"):
    settings.aggiorna(lambda d: d.__setitem__("limesurvey", {"url": "https://prova.limesurvey.net", "utente": "luca", "password": password}))


def test_client_e_import(monkeypatch):
    configura()
    assert limesurvey.prova(T)["sondaggi"] == 1
    s = limesurvey.elenco(T)[0]
    assert s["titolo"] == "Clima interno 2027" and s["completate"] == 29
    csv_testo, et = limesurvey.scarica("445566", T, forza=True)
    assert "G01" in csv_testo and et["G01"] == "In quale area lavora?"

    # le API usano il client reale: lo si collega al server simulato
    vero = limesurvey._client
    monkeypatch.setattr(limesurvey, "_client", lambda transport=None: vero(T))
    c = TestClient(app)
    a = c.post("/api/limesurvey/anteprima", json={"sid": "445566"}).json()
    assert a["righe"] == 29 and "Q01" in a["numeriche"] and a["etichette"]["Q03"].startswith("Quanta fiducia")
    r = c.post("/api/limesurvey/importa", json={"sid": "445566", "titolo": "Clima interno 2027", "nome": "Clima LS",
                                                 "colonna_gruppo": "G01", "colonne_clima": ["Q01", "Q02"], "colonna_fiducia": "Q03"})
    assert r.status_code == 200, r.text
    m = c.get(f"/api/mondi/{r.json()['id']}").json()
    nomi = {p["nome"] for p in m["personas"]}
    assert nomi == {"Operativi su strada", "Uffici"}  # «Direzione» ha solo 4 risposte: esclusa per anonimato
    assert m["fonte"]["sid"] == "445566"
    uffici = next(p for p in m["personas"] if p["nome"] == "Uffici")
    strada = next(p for p in m["personas"] if p["nome"] == "Operativi su strada")
    assert uffici["atteggiamento"] > strada["atteggiamento"] and uffici["fiducia"] > strada["fiducia"]
    # il mondo creato si può subito stimolare
    sim = c.post("/api/simula", json={"mondo_id": m["id"], "messaggio": "Dal 2027 nuovo piano welfare per tutti.", "canale": m["canali"][0]["id"]})
    assert sim.status_code == 200
    settings.FILE.unlink()


def test_password_sbagliata():
    configura("sbagliata")
    try:
        limesurvey.prova(T)
        assert False
    except limesurvey.ErroreLimeSurvey as e:
        assert "non corretti" in str(e)
    settings.FILE.unlink()
