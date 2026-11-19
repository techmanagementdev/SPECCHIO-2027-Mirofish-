"use strict";
const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
async function api(path, metodo = "GET", body) {
  const r = await fetch(path, { method: metodo, headers: body !== undefined ? { "Content-Type": "application/json" } : {}, body: body !== undefined ? JSON.stringify(body) : undefined });
  if (r.status === 401) { location.href = "/login?area=admin"; throw new Error("Accesso richiesto"); }
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) { /* */ } throw new Error(typeof m === "string" ? m : JSON.stringify(m)); }
  return r.json();
}
function esito(id, ok, testo) { $("#" + id + "-ok").textContent = ok ? testo : ""; $("#" + id + "-err").textContent = ok ? "" : testo; }
const NOMI = { anthropic: "Anthropic", openai: "compatibile OpenAI", mock: "solo regole (dimostrativa)" };
let cur = null;

async function carica() {
  const d = await api("/api/admin/impostazioni");
  const s = d.statistiche;
  $("#stat").innerHTML = [["Simulazioni", s.simulazioni], ["Dialoghi", s.dialoghi], ["Importazioni", s.importazioni], ["Ultimo uso", s.ultimo_uso || "—"]]
    .map(([l, v]) => `<div class="kpi"><span>${l}</span><b>${esc(v)}</b></div>`).join("");
  const l = d.llm;
  $("#llm-attivo").textContent = NOMI[l.attivo] || l.attivo;
  $("#provider").value = l.provider || "";
  for (const k of ["anthropic_model", "openai_model", "openai_base_url"]) $("#" + k).value = l[k] || "";
  for (const k of ["anthropic_key", "openai_key"]) { $("#" + k).value = ""; $("#" + k).placeholder = l[k] || "non impostata"; }
  $("#ls-url").value = d.limesurvey.url || ""; $("#ls-utente").value = d.limesurvey.utente || "";
  $("#ls-password").value = ""; $("#ls-password").placeholder = d.limesurvey.password || "non impostata";
  $("#p-round").value = d.simulazione.round; $("#p-esec").value = d.simulazione.esecuzioni; $("#p-max").value = d.simulazione.max_agenti;
  $("#mondi").innerHTML = d.mondi.map((m) => `<tr><td><b>${esc(m.nome)}</b><br><small class="muted">${esc(m.id)}</small></td><td>${m.tipo === "citta" ? "città" : "organizzazione"}</td><td>${m.personas}</td>
    <td><span class="badge-or ${m.origine}">${m.origine}</span></td>
    <td><input type="checkbox" data-vis="${esc(m.id)}" ${m.visibile ? "checked" : ""} aria-label="Visibile"></td>
    <td class="az"><button data-ed="${esc(m.id)}" title="Modifica"><i class="ti ti-edit"></i></button> <button data-dl="${esc(m.id)}" title="Scarica"><i class="ti ti-download"></i></button>
    ${m.origine !== "predefinito" ? `<button data-del="${esc(m.id)}" title="${m.origine === "modificato" ? "Torna alla versione predefinita" : "Elimina"}"><i class="ti ti-${m.origine === "modificato" ? "arrow-back-up" : "trash"}"></i></button>` : ""}</td></tr>`).join("");
  document.querySelectorAll("[data-vis]").forEach((c) => (c.onchange = async () => { try { await api(`/api/admin/mondi/${c.dataset.vis}/visibile`, "POST", { visibile: c.checked }); esito("m", true, c.checked ? "Mondo visibile agli utenti" : "Mondo nascosto agli utenti"); } catch (e) { esito("m", false, e.message); } }));
  document.querySelectorAll("[data-ed]").forEach((b) => (b.onclick = () => apriEditor(b.dataset.ed)));
  document.querySelectorAll("[data-dl]").forEach((b) => (b.onclick = () => scarica(b.dataset.dl)));
  document.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Confermi? Le modifiche a questo mondo andranno perse.")) return;
    try { await api(`/api/admin/mondi/${b.dataset.del}`, "DELETE"); esito("m", true, "Fatto"); carica(); } catch (e) { esito("m", false, e.message); }
  }));
}

$("#salva-llm").onclick = async () => {
  const body = { provider: $("#provider").value, anthropic_model: $("#anthropic_model").value, openai_model: $("#openai_model").value, openai_base_url: $("#openai_base_url").value };
  for (const k of ["anthropic_key", "openai_key"]) { const v = $("#" + k).value.trim(); if (v === "-") body[k] = ""; else if (v) body[k] = v; }
  try { const r = await api("/api/admin/llm", "POST", body); esito("llm", true, "Salvato. Modello attivo: " + (NOMI[r.attivo] || r.attivo)); carica(); } catch (e) { esito("llm", false, e.message); }
};
$("#prova-llm").onclick = async () => {
  esito("llm", true, "Prova in corso…");
  try { const r = await api("/api/admin/llm/prova", "POST", {}); esito("llm", true, `Collegamento riuscito con ${NOMI[r.fornitore] || r.fornitore} in ${r.secondi} s. Risposta: «${r.risposta}»`); } catch (e) { esito("llm", false, e.message); }
};
$("#salva-ls").onclick = async () => {
  const body = { url: $("#ls-url").value, utente: $("#ls-utente").value };
  const pw = $("#ls-password").value; if (pw) body.password = pw;
  try { const r = await api("/api/admin/limesurvey", "POST", body); esito("ls", true, r.configurato ? "Salvato. Ora prova il collegamento." : "Salvato, ma mancano dei dati."); carica(); } catch (e) { esito("ls", false, e.message); }
};
$("#prova-ls").onclick = async () => {
  esito("ls", true, "Collegamento in corso…");
  try { const r = await api("/api/admin/limesurvey/prova", "POST", {}); esito("ls", true, `Collegato: ${r.sondaggi} sondaggi trovati.`); } catch (e) { esito("ls", false, e.message); }
};
$("#salva-sim").onclick = async () => {
  try { await api("/api/admin/simulazione", "POST", { round: +$("#p-round").value, esecuzioni: +$("#p-esec").value, max_agenti: +$("#p-max").value }); esito("sim", true, "Parametri salvati"); } catch (e) { esito("sim", false, e.message); }
};
$("#salva-pw").onclick = async () => {
  const u = $("#pw-utente").value, a = $("#pw-admin").value;
  if (!u && !a) { esito("pw", false, "Scrivi almeno una nuova password."); return; }
  try {
    if (u) await api("/api/admin/password", "POST", { ruolo: "utente", nuova: u });
    if (a) await api("/api/admin/password", "POST", { ruolo: "admin", nuova: a });
    $("#pw-utente").value = ""; $("#pw-admin").value = ""; esito("pw", true, "Password aggiornate");
  } catch (e) { esito("pw", false, e.message.includes("at least") ? "La password deve avere almeno 8 caratteri." : e.message); }
};

async function apriEditor(id) {
  try {
    const m = await api("/api/admin/mondi/" + id);
    cur = id; $("#editor").hidden = false; $("#ed-tit").textContent = "Modifica: " + m.nome;
    $("#ed-json").value = JSON.stringify(m, null, 2); $("#ed-err").textContent = "";
    $("#editor").scrollIntoView({ behavior: "smooth" });
  } catch (e) { esito("m", false, e.message); }
}
$("#ed-chiudi").onclick = () => { $("#editor").hidden = true; cur = null; };
$("#ed-salva").onclick = async () => {
  let m;
  try { m = JSON.parse($("#ed-json").value); } catch (e) { $("#ed-err").textContent = "Il testo non è un JSON valido: " + e.message; return; }
  try { await api("/api/admin/mondi/" + cur, "PUT", m); $("#ed-err").textContent = ""; esito("m", true, "Mondo salvato"); $("#editor").hidden = true; carica(); } catch (e) { $("#ed-err").textContent = e.message; }
};
async function scarica(id) {
  const m = await api("/api/admin/mondi/" + id);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(m, null, 2)], { type: "application/json" }));
  a.download = id + ".json"; a.click(); URL.revokeObjectURL(a.href);
}
$("#carica").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  try { const m = JSON.parse(await f.text()); const r = await api("/api/admin/mondi", "POST", m); esito("m", true, "Mondo caricato: " + r.id); carica(); }
  catch (err) { esito("m", false, "Caricamento non riuscito: " + err.message); }
  e.target.value = "";
};
$("#esci").onclick = async () => { await fetch("/api/logout", { method: "POST" }); location.href = "/login?area=admin"; };
carica().catch((e) => esito("m", false, e.message));
