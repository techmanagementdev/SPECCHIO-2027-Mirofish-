"""Mondi (città o organizzazioni), personas e popolazione di agenti."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PRESET_DIR = BASE / "presets"
from .settings import DATA_DIR

USER_DIR = DATA_DIR / "mondi_utente"

CANALE_PASSAPAROLA = "passaparola"


def _carica_dir(d: Path) -> dict[str, dict]:
    out = {}
    if d.exists():
        for f in sorted(d.glob("*.json")):
            mondo = json.loads(f.read_text(encoding="utf-8"))
            out[mondo["id"]] = mondo
    return out


def elenco_mondi() -> dict[str, dict]:
    mondi = _carica_dir(PRESET_DIR)
    mondi.update(_carica_dir(USER_DIR))
    return mondi


def carica_mondo(mondo_id: str) -> dict:
    mondi = elenco_mondi()
    if mondo_id not in mondi:
        raise KeyError(f"Mondo non trovato: {mondo_id}")
    return mondi[mondo_id]


def origine(mondo_id: str) -> str:
    if (USER_DIR / f"{mondo_id}.json").exists():
        return "modificato" if (PRESET_DIR / f"{mondo_id}.json").exists() else "creato"
    return "predefinito"


def elimina_mondo_utente(mondo_id: str) -> bool:
    f = USER_DIR / f"{mondo_id}.json"
    if f.exists():
        f.unlink()
        return True
    return False


def valida_mondo(m: dict) -> list[str]:
    errori = []
    for k in ["id", "nome", "tipo", "unita", "canali", "personas", "composizione"]:
        if k not in m:
            errori.append(f"manca il campo «{k}»")
    if errori:
        return errori
    ids = {p.get("id") for p in m["personas"]}
    for p in m["personas"]:
        for k in ["id", "nome", "atteggiamento", "fiducia", "scetticismo", "influenza"]:
            if k not in p:
                errori.append(f"persona {p.get('id', '?')}: manca «{k}»")
    unita = {u.get("id") for u in m["unita"]}
    for u, mix in m["composizione"].items():
        if u not in unita:
            errori.append(f"composizione: unità «{u}» non definita")
        for pid in mix:
            if pid not in ids:
                errori.append(f"composizione: persona «{pid}» non definita")
    if not m["canali"]:
        errori.append("serve almeno un canale")
    return errori


def salva_mondo_utente(mondo: dict) -> None:
    USER_DIR.mkdir(parents=True, exist_ok=True)
    (USER_DIR / f"{mondo['id']}.json").write_text(json.dumps(mondo, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass
class Agente:
    idx: int
    persona_id: str
    unita_id: str
    atteggiamento: float
    fiducia: float
    scetticismo: float
    influenza: float
    informato: bool = False
    via: str = ""  # canale o passaparola
    sentiment: float = 0.0
    propria: float = 0.0
    bias: float = 0.0
    vicini: list[int] = field(default_factory=list)


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def costruisci_popolazione(mondo: dict, composizione: dict | None, rng: random.Random, max_agenti: int | None = None) -> list[Agente]:
    """Crea gli agenti secondo la composizione {unita_id: {persona_id: numero}}."""
    personas = {p["id"]: p for p in mondo["personas"]}
    if max_agenti is None:
        from .settings import carica
        max_agenti = int(carica()["simulazione"].get("max_agenti", 400))
    comp = composizione or mondo["composizione"]
    totale = sum(sum(v.values()) for v in comp.values()) or 1
    scala = min(1.0, max_agenti / totale)
    agenti: list[Agente] = []
    for unita_id, mix in comp.items():
        for pid, n in mix.items():
            if pid not in personas:
                continue
            p = personas[pid]
            for _ in range(max(0, round(n * scala))):
                agenti.append(Agente(
                    idx=len(agenti), persona_id=pid, unita_id=unita_id,
                    atteggiamento=_clip(p["atteggiamento"] + rng.gauss(0, 0.12), -1, 1),
                    fiducia=_clip(p["fiducia"] + rng.gauss(0, 0.08), 0, 1),
                    scetticismo=_clip(p["scetticismo"] + rng.gauss(0, 0.08), 0, 1),
                    influenza=_clip(p["influenza"] + rng.gauss(0, 0.1), 0, 1),
                    bias=rng.gauss(0, 0.28),
                ))
    for a in agenti:
        a.sentiment = 0.4 * a.atteggiamento
    _collega(agenti, rng)
    return agenti


def _collega(agenti: list[Agente], rng: random.Random) -> None:
    """Rete sociale: legami soprattutto dentro la stessa unità, alcuni ponti tra unità.
    Gli agenti più influenti hanno più legami."""
    per_unita: dict[str, list[Agente]] = {}
    for a in agenti:
        per_unita.setdefault(a.unita_id, []).append(a)
    for a in agenti:
        stessi = per_unita[a.unita_id]
        k_in = 3 + round(5 * a.influenza)
        for b in rng.sample(stessi, min(k_in, len(stessi))):
            if b.idx != a.idx and b.idx not in a.vicini:
                a.vicini.append(b.idx)
                b.vicini.append(a.idx)
        if rng.random() < 0.25 + 0.5 * a.influenza and len(per_unita) > 1:
            b = rng.choice(agenti)
            if b.idx != a.idx and b.idx not in a.vicini:
                a.vicini.append(b.idx)
                b.vicini.append(a.idx)
