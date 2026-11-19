"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const r0 = (v) => Math.round(v);
const RID = location.pathname.split("/").pop();
const S = { report: null, mondo: null, tipo: null, canale: null, chatP: null, chat: {}, prove: [], ultimo: null };

async function api(path, body) {
  const r = await fetch(`/api/r/${RID}${path}`, body !== undefined ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (r.status === 401) { mostraAccesso(); throw new Error("Accesso richiesto"); }
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) { /* */ } throw new Error(typeof m === "string" ? m : "Errore"); }
  return r.json();
}
const colore = (v) => (v >= 70 ? "verde" : v >= 50 ? "giallo" : "rosso");
const emojiVal = (v) => (v >= 70 ? "🟢" : v >= 50 ? "🟡" : "🔴");
const faccia = (v) => (v >= 62 ? "😊" : v >= 52 ? "🙂" : v >= 45 ? "😐" : v >= 35 ? "😟" : "😠");

// ---------------- accesso
function mostraAccesso() { $("#accesso").hidden = false; $("#app").hidden = true; }
$("#f-accesso").onsubmit = async (e) => {
  e.preventDefault(); $("#err-accesso").textContent = "";
  const r = await fetch(`/api/r/${RID}/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ codice: $("#codice").value }) });
  if (r.ok) { $("#accesso").hidden = true; avvia(); return; }
  let m = "Codice non corretto"; try { m = (await r.json()).detail || m; } catch (x) { /* */ }
  $("#err-accesso").textContent = typeof m === "string" ? m : "Codice non valido";
};
$("#esci").onclick = async () => { await fetch(`/api/r/${RID}/esci`, { method: "POST" }); location.reload(); };
$$(".schede button").forEach((b) => (b.onclick = () => {
  $$(".schede button").forEach((x) => x.classList.toggle("on", x === b));
  $$(".sez").forEach((s) => s.classList.toggle("on", s.id === "s-" + b.dataset.s));
  window.scrollTo(0, 0);
}));

// ---------------- risultati
function disegnaRisultati() {
  const r = S.report;
  $("#cliente").textContent = r.cliente || "Report";
  $("#titolo").textContent = r.titolo;
  $("#meta").textContent = `${r.risposte} risposte · aggiornato al ${r.creato}`;
  document.title = r.titolo;
  if (r.indice != null) {
    $("#faccia").textContent = { verde: "😊", giallo: "😐", rosso: "😟" }[r.semaforo.colore];
    $("#indice").textContent = r0(r.indice);
    $("#semaforo").className = "pill " + r.semaforo.colore;
    $("#semaforo").textContent = `${r.semaforo.emoji} ${r.semaforo.etichetta}`;
  }
  $("#in-breve").innerHTML = r.in_breve.filter((b) => !b.titolo.startsWith("Indice complessivo")).map((b) => `<div class="card"><div class="e">${b.emoji}</div><b>${esc(b.titolo)}</b><p>${esc(b.testo)}</p></div>`).join("");
  $("#legenda").innerHTML = r.legenda.map((l) => `<span>${l.emoji} ${esc(l.testo)}</span>`).join("");
  $("#domande").innerHTML = r.domande.map((d) => {
    const neutri = Math.max(0, 100 - d.favorevoli - d.critici);
    return `<div class="dom"><div class="riga"><span class="e">${d.emoji}</span><span class="t">${esc(d.testo)}</span><span class="v">${r0(d.punteggio)}</span></div>
      <div class="barra"><div class="${d.colore}-bg" style="width:0" data-w="${d.punteggio}"></div></div>
      <div class="distr"><div class="verde-bg" style="width:${d.favorevoli}%"></div><div class="grigio-bg" style="width:${neutri}%"></div><div class="rosso-bg" style="width:${d.critici}%"></div></div>
      <div class="leg">👍 ${d.favorevoli}% d'accordo · 😐 ${neutri}% a metà · 👎 ${d.critici}% non d'accordo · ${d.etichetta} · media ${String(d.media).replace(".", ",")} su ${d.scala[1]}</div></div>`;
  }).join("");
  requestAnimationFrame(() => $$(".barra div[data-w]").forEach((b) => (b.style.width = b.dataset.w + "%")));
  $("#gruppo-spiega").textContent = `Indice per ${r.gruppo.toLowerCase()}. Ogni gruppo ha almeno 10 risposte.`;
  $("#gruppi").innerHTML = r.gruppi.filter((g) => g.indice != null).map((g) => `<div class="card"><div class="e">${faccia(g.indice)}</div><div class="nome">${esc(g.nome)}</div><div class="num">${r0(g.indice)}</div><small>${g.n} risposte · ${g.emoji} ${g.etichetta}</small>
    <div class="barra"><div class="${colore(g.indice)}-bg" style="width:${g.indice}%"></div></div></div>`).join("");
  const gs = r.gruppi.filter((g) => g.indice != null).map((g) => g.nome);
  if (gs.length > 1) {
    $("#mappa").innerHTML = `<tr><th>Domanda</th>${gs.map((g) => `<th>${esc(g)}</th>`).join("")}</tr>` + r.domande.map((d) => `<tr><td class="q">${d.emoji} ${esc(d.breve)}</td>${gs.map((g) => { const v = d.per_gruppo[g]; return v == null ? `<td class="c-vuoto">—</td>` : `<td class="c-${colore(v)}">${r0(v)}</td>`; }).join("")}</tr>`).join("");
  }
  $("#categoriali").innerHTML = r.categoriali.map((c) => `<h3>${c.multipla ? "☑️" : "🗂️"} ${esc(c.testo)}</h3>${c.multipla ? `<p class="spiega">Quota di chi ha indicato ciascuna voce (più risposte possibili).</p>` : ""}<div class="card cat">${c.voci.map((v) => `<div class="cvoce"><span>${esc(v.etichetta)}</span><div class="barra" style="margin:0"><div class="blu" style="width:${v.quota}%;background:var(--blu)"></div></div><b>${v.quota}%</b></div>`).join("")}</div>`).join("");
  $("#nota").textContent = r.nota;
}

// ---------------- personas
const NOMI_CAN = () => ({ ...Object.fromEntries(S.mondo.canali.map((c) => [c.id, c.nome])), passaparola: "Passaparola" });
function disegnaPersonas() {
  const tot = {}; let T = 0;
  for (const mix of Object.values(S.mondo.composizione)) for (const [p, n] of Object.entries(mix)) { tot[p] = (tot[p] || 0) + n; T += n; }
  const nc = NOMI_CAN();
  const lista = (titolo, arr) => (arr && arr.length ? `<div class="blocco"><b>${titolo}</b><ul>${arr.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>` : "");
  $("#personas").innerHTML = S.mondo.personas.map((p) => {
    const mood = p.atteggiamento > 0.2 ? "😊" : p.atteggiamento < -0.2 ? "😟" : "😐";
    const canali = Object.entries(p.canali || {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k]) => nc[k] || k);
    return `<div class="pers">
      <div class="top"><span class="av" style="background:${p.colore}">${esc(p.avatar || "")}</span><div><h3>${esc(p.nome)}</h3><div class="peso">${T ? r0((100 * (tot[p.id] || 0)) / T) : 0}% delle persone · fiducia ${r0(p.fiducia * 100)}/100</div></div><span class="mood" title="Atteggiamento">${mood}</span></div>
      <p class="cat">${esc(p.descrizione || "")}</p>
      ${lista("💪 Cosa apprezza", p.punti_forza)}${lista("⚠️ Cosa lo preoccupa", p.criticita)}${lista("🙏 Cosa chiede", p.aspettative)}
      <div class="blocco"><b>📣 Come raggiungerlo</b><ul><li>${canali.map(esc).join(", ")}</li></ul></div>
      <button data-p="${p.id}">💬 Parla con questa persona</button></div>`;
  }).join("");
  $$("#personas button[data-p]").forEach((b) => (b.onclick = () => apriChat(b.dataset.p)));
}
const DOMANDE = ["Qual è il problema principale per te?", "Che cosa ti manca?", "Come preferisci essere informato?", "Cosa pensi dell'ultimo messaggio che ho provato?"];
function apriChat(pid) {
  S.chatP = pid; const p = S.mondo.personas.find((x) => x.id === pid);
  $("#chat").hidden = false;
  $("#chat-testa").innerHTML = `<span class="av" style="background:${p.colore};width:44px;height:44px;border-radius:14px;color:#fff;display:grid;place-items:center">${esc(p.avatar || "")}</span> 💬 ${esc(p.nome)}`;
  $("#domande-rapide").innerHTML = DOMANDE.map((d) => `<button>${esc(d)}</button>`).join("");
  $$("#domande-rapide button").forEach((b) => (b.onclick = () => chiedi(b.textContent)));
  disegnaMsgs(); $("#chat").scrollIntoView({ behavior: "smooth" });
}
function disegnaMsgs() {
  const st = S.chat[S.chatP] || [];
  $("#msgs").innerHTML = st.length ? st.map((m) => `<div class="m ${m.role === "user" ? "u" : "a"}">${esc(m.content)}</div>`).join("") : `<p class="spiega">Fai una domanda o scegline una qui sotto. Le risposte sono simulate dal profilo.</p>`;
  $("#msgs").scrollTop = 1e6;
}
async function chiedi(t) {
  t = t.trim(); $("#err-chat").textContent = "";
  if (!t) { $("#err-chat").textContent = "Scrivi una domanda."; return; }
  const st = (S.chat[S.chatP] = S.chat[S.chatP] || []);
  st.push({ role: "user", content: t }); disegnaMsgs();
  try {
    const r = await api("/chat", { persona_id: S.chatP, domanda: t, storia: st.slice(0, -1), contesto_messaggio: S.ultimo ? S.ultimo.messaggio : null });
    st.push({ role: "assistant", content: r.risposta }); disegnaMsgs();
  } catch (e) { $("#err-chat").textContent = e.message; }
}
$("#f-chat").onsubmit = (e) => { e.preventDefault(); const v = $("#chat-in").value; $("#chat-in").value = ""; chiedi(v); };

// ---------------- impact simulation
const TIPI = [
  { id: "annuncio", e: "📢", nome: "Annuncio ufficiale", parole: ["sito", "bacheca", "comunicato", "email"], esempio: "Dal [data] cambia [cosa]. Ecco perché e cosa significa per voi: …" },
  { id: "email", e: "✉️", nome: "E-mail o lettera", parole: ["email", "sito", "bacheca"], esempio: "Gentili colleghi, vi scriviamo per informarvi che …" },
  { id: "social", e: "📱", nome: "Post sui social", parole: ["social", "gruppi", "app"], esempio: "Novità in arrivo: … Scopri di più e dicci cosa ne pensi!" },
  { id: "incontro", e: "🗣️", nome: "Incontro o assemblea", parole: ["incontro", "assemblea", "responsabile"], esempio: "Vi invitiamo all'incontro del [data] per presentare … e raccogliere le vostre proposte." },
  { id: "stampa", e: "📰", nome: "Notizia sulla stampa", parole: ["giornale", "tv_radio", "stampa", "bacheca"], esempio: "[Ente] annuncia … L'intervento partirà il … e riguarderà …" },
  { id: "proposta", e: "💡", nome: "Proposta o nuova misura", parole: ["assemblea", "incontro", "responsabile", "sito"], esempio: "Proponiamo di … Prima di decidere vogliamo ascoltare le vostre opinioni entro il …" },
];
function canalePer(tipo) {
  for (const p of tipo.parole) { const c = S.mondo.canali.find((x) => x.id.includes(p) || x.nome.toLowerCase().includes(p)); if (c) return c.id; }
  return S.mondo.canali[0].id;
}
function disegnaImpact() {
  $("#tipi").innerHTML = TIPI.map((t) => `<button data-t="${t.id}" class="${S.tipo === t.id ? "on" : ""}"><span>${t.e}</span>${t.nome}</button>`).join("");
  $$("#tipi button").forEach((b) => (b.onclick = () => {
    const t = TIPI.find((x) => x.id === b.dataset.t); S.tipo = t.id; S.canale = canalePer(t);
    if (!$("#msg").value.trim()) $("#msg").placeholder = t.esempio;
    disegnaImpact();
  }));
  $("#canali").innerHTML = S.mondo.canali.map((c) => `<button data-c="${c.id}" class="${S.canale === c.id ? "on" : ""}">${esc(c.nome)}</button>`).join("");
  $$("#canali button").forEach((b) => (b.onclick = () => { S.canale = b.dataset.c; disegnaImpact(); }));
  $("#esempi").innerHTML = (S.mondo.esempi || []).map((e, i) => `<button data-i="${i}">✨ ${esc(e.titolo)}</button>`).join("");
  $$("#esempi button").forEach((b) => (b.onclick = () => { const e = S.mondo.esempi[+b.dataset.i]; $("#msg").value = e.testo; S.canale = e.canale; disegnaImpact(); }));
}
$("#simula").onclick = async () => {
  const t = $("#msg").value.trim(); $("#err-sim").textContent = "";
  if (t.length < 3) { $("#err-sim").textContent = "Scrivi il messaggio da provare."; return; }
  if (!S.canale) S.canale = S.mondo.canali[0].id;
  $("#simula").disabled = true; $("#simula").textContent = "⏳ Simulazione in corso…";
  try {
    const r = await api("/simula", { messaggio: t, canale: S.canale });
    S.ultimo = r;
    const tipo = TIPI.find((x) => x.id === S.tipo);
    S.prove.push({ e: tipo ? tipo.e : "📝", testo: t, canale: r.canale.nome, indice: r.finale.indice });
    mostraEsito(r); disegnaProve();
  } catch (e) { $("#err-sim").textContent = e.message; }
  finally { $("#simula").disabled = false; $("#simula").textContent = "🚀 Simula l'impatto"; }
};
function verdetto(v, neg) {
  if (v >= 62 && neg < 20) return ["Il messaggio funziona", "La maggior parte delle persone lo accoglie bene."];
  if (v >= 52) return ["Funziona, ma si può migliorare", "Una parte delle persone resta dubbiosa: guarda le obiezioni."];
  if (v >= 45) return ["Accoglienza tiepida", "Il messaggio non convince: rivedi contenuto o canale."];
  return ["Rischio di reazione negativa", "Così com'è il messaggio rischia di peggiorare il clima."];
}
function mostraEsito(r) {
  const f = r.finale, [tit, sott] = verdetto(f.indice, f.negativi);
  $("#esito").hidden = false;
  $("#verdetto").innerHTML = `<span class="e">${faccia(f.indice)}</span><span class="num">${r0(f.indice)}</span><div class="txt"><b>${tit}</b><span>${sott}</span><div class="stelle">${"★".repeat(r.stelle)}${"☆".repeat(3 - r.stelle)}</div></div>`;
  $("#kpi3").innerHTML = `<div class="card"><div class="e">👍</div><b>${r0(f.positivi)}%</b><span>favorevoli</span></div><div class="card"><div class="e">👎</div><b>${r0(f.negativi)}%</b><span>contrari</span></div><div class="card"><div class="e">📣</div><b>${r0(f.raggiunti_canale)}%</b><span>raggiunti subito dal canale</span></div>`;
  const frasi = Object.fromEntries(r.frasi.map((q) => [q.persona_id, q.testo]));
  $("#reazioni").innerHTML = [...r.personas].sort((a, b) => (b.indice ?? 50) - (a.indice ?? 50)).map((p) => {
    const v = p.indice ?? 50;
    return `<div class="reaz"><span class="e">${faccia(v)}</span><span class="n">${esc(p.nome)}</span><div class="barra" style="margin:0"><div class="${v >= 55 ? "verde" : v >= 45 ? "giallo" : "rosso"}-bg" style="width:${v}%"></div></div><span class="v">${r0(v)}</span>${frasi[p.id] ? `<q>${esc(frasi[p.id])}</q>` : ""}</div>`;
  }).join("");
  $("#obiezioni").innerHTML = r.obiezioni.length ? r.obiezioni.map((o) => `<div class="ob">⚠️ ${esc(o.testo)} <small>(${o.quota}%)</small></div>`).join("") : `<div class="ob">✅ Nessuna obiezione rilevante.</div>`;
  $("#consigli").innerHTML = r.consigli.map((c) => `<div class="tip">💡 ${esc(c)}</div>`).join("");
  $("#voci").innerHTML = r.voci.map((v) => `<div class="voce">👂 ${esc(v)}</div>`).join("");
  const serie = r.serie.indice.media;
  $("#rounds").innerHTML = serie.map((v, i) => `<div class="${v >= 55 ? "verde" : v >= 45 ? "giallo" : "rosso"}-bg" style="height:${Math.max(4, v)}%"><span>${r0(v)}</span><i>${i === 0 ? "annuncio" : i}</i></div>`).join("");
  $("#avvertenza").textContent = r.avvertenza;
  $("#esito").scrollIntoView({ behavior: "smooth" });
}
function disegnaProve() {
  $("#prove-box").hidden = S.prove.length < 1;
  const ord = [...S.prove].sort((a, b) => b.indice - a.indice);
  $("#prove").innerHTML = ord.map((p, i) => `<div class="prova ${i === 0 && S.prove.length > 1 ? "migliore" : ""}"><span style="font-size:26px">${i === 0 && S.prove.length > 1 ? "🏆" : p.e}</span><span>${esc(p.testo.slice(0, 110))}${p.testo.length > 110 ? "…" : ""}<br><small style="color:var(--muted)">${esc(p.canale)}</small></span><span>${faccia(p.indice)}</span><span class="v">${r0(p.indice)}</span></div>`).join("");
}

// ---------------- avvio
async function avvia() {
  try {
    const d = await api("");
    S.report = d.report; S.mondo = d.mondo;
    $("#app").hidden = false; $("#accesso").hidden = true;
    disegnaRisultati(); disegnaPersonas(); disegnaImpact();
  } catch (e) { if (e.message !== "Accesso richiesto") document.body.innerHTML = `<div class="accesso"><div class="box"><div class="big-emoji">🔎</div><h1>Report non disponibile</h1><p>${esc(e.message)}</p></div></div>`; }
}
avvia();
