"""Accesso protetto e area riservata."""
from fastapi.testclient import TestClient

from app import settings
from app.main import app


def test_accesso_e_area_riservata(monkeypatch):
    monkeypatch.setenv("ACCESS_PASSWORD", "utente-prova-1")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-prova-1")
    c = TestClient(app)
    assert c.get("/api/stato").status_code == 401
    home = c.get("/")
    assert home.status_code == 200 and "SPECCHIO" in home.text and 'href="/login"' in home.text
    r = c.get("/app", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert c.get("/login").status_code == 200
    assert c.post("/api/login", json={"password": "sbagliata", "area": "utente"}).status_code == 401

    assert c.post("/api/login", json={"password": "utente-prova-1", "area": "utente"}).status_code == 200
    assert c.get("/api/stato").json()["ruolo"] == "utente"
    assert c.get("/app").status_code == 200
    assert c.get("/api/admin/impostazioni").status_code == 401
    assert c.get("/admin", follow_redirects=False).status_code == 303

    assert c.post("/api/login", json={"password": "admin-prova-1", "area": "admin"}).status_code == 200
    d = c.get("/api/admin/impostazioni").json()
    assert {m["id"] for m in d["mondi"]} >= {"aaa-interno", "citta-esempio"}

    # chiave salvata ma mai restituita per intero
    assert c.post("/api/admin/llm", json={"provider": "mock", "openai_key": "sk-segreta-1234"}).status_code == 200
    assert c.get("/api/admin/impostazioni").json()["llm"]["openai_key"].endswith("1234")
    assert "sk-segreta" not in c.get("/api/admin/impostazioni").text

    # nascondere un mondo agli utenti
    c.post("/api/admin/mondi/citta-esempio/visibile", json={"visibile": False})
    u = TestClient(app)
    u.post("/api/login", json={"password": "utente-prova-1", "area": "utente"})
    assert "citta-esempio" not in {m["id"] for m in u.get("/api/mondi").json()}
    assert u.get("/api/mondi/citta-esempio").status_code == 404
    c.post("/api/admin/mondi/citta-esempio/visibile", json={"visibile": True})

    # modifica di un mondo con validazione
    m = c.get("/api/admin/mondi/citta-esempio").json()
    m["nome"] = "Borgo Nuovo modificato"
    assert c.put("/api/admin/mondi/citta-esempio", json=m).status_code == 200
    assert c.get("/api/mondi/citta-esempio").json()["nome"] == "Borgo Nuovo modificato"
    rotto = dict(m, composizione={"centro": {"fantasma": 3}})
    assert c.put("/api/admin/mondi/citta-esempio", json=rotto).status_code == 400
    assert c.delete("/api/admin/mondi/citta-esempio").status_code == 200
    assert c.get("/api/mondi/citta-esempio").json()["nome"].startswith("Borgo Nuovo ·")

    # cambio password
    assert c.post("/api/admin/password", json={"ruolo": "utente", "nuova": "nuova-pass-99"}).status_code == 200
    n = TestClient(app)
    assert n.post("/api/login", json={"password": "utente-prova-1", "area": "utente"}).status_code == 401
    assert n.post("/api/login", json={"password": "nuova-pass-99", "area": "utente"}).status_code == 200
    settings.FILE.unlink()  # ripristina lo stato per gli altri test
