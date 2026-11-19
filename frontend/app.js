"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const f1 = (v) => (Math.round(v * 10) / 10).toLocaleString("it-IT");
const f0 = (v) => Math.round(v).toLocaleString("it-IT");
const POS = "#1baf7a", NEG = "#e34948", NEU = "#c9c7bd";

const S = { mondi: [], mondo: null, comp: null, unita: null, canale: null, bersaglio: new Set(), ris: null, chat: {}, chatP: null, llm: false };

// ---------- progressi (salvati nel browser) ----------
const BADGE = [
  { id: "primo", nome: "Primo lancio", icona: "rocket", desc: "Hai lanciato il primo annuncio" },
  { id: "tre-stelle", nome: "Tre stelle", icona: "stars", desc: "Un annuncio da tre stelle" },
  { id: "ascoltatore", nome: "Buon ascoltatore", icona: "ear", desc: "Hai fatto 5 domande alle personas" },
  { id: "stratega", nome: "Stratega A/B", icona: "swords", desc: "Hai completato una sfida A/B" },
  { id: "costruttore", nome: "Costruttore", icona: "building-community", desc: "Hai cambiato la composizione e lanciato un annuncio" },
  { id: "analista", nome: "Analista dei dati", icona: "database-import", desc: "Hai creato un mondo da dati reali" },
  { id: "missione", nome: "Missione compiuta", icona: "target-arrow", desc: "Hai completato una missione" },
];
let P = { xp: 0, badge: [], missioni: {}, domande: 0, compModificata: false };
try { P = { ...P, ...JSON.parse(localStorage.getItem("specchio-progressi") || "{}") }; } catch (e) { /* storage non disponibile */ }
function salva() { try { localStorage.setItem("specchio-progressi", JSON.stringify(P)); } catch (e) { /* ignora */ } }
function toast(html) { const d = document.createElement("div"); d.innerHTML = html; $("#toast").appendChild(d); setTimeout(() => d.remove(), 3500); }
function aggiungiXp(n, motivo) {
  const prima = Math.floor(P.xp / 100);
  P.xp += n; salva(); disegnaPlayer();
  if (motivo) toast(`<i class="ti ti-sparkles"></i> +${n} XP · ${esc(motivo)}`);
  if (Math.floor(P.xp / 100) > prima) toast(`<i class="ti ti-arrow-big-up-lines"></i> Sei salito al livello ${Math.floor(P.xp / 100) + 1}`);
}
function badge(id) {
  if (P.badge.includes(id)) return;
  P.badge.push(id); salva();
  const b = BADGE.find((x) => x.id === id);
  toast(`<i class="ti ti-${b.icona}"></i> Nuovo badge: ${esc(b.nome)}`);
  aggiungiXp(20); disegnaPlayer(); disegnaMissioni();
}
function disegnaPlayer() {
  $("#livello").textContent = Math.floor(P.xp / 100) + 1;
  $("#xpfill").style.width = (P.xp % 100) + "%";
  $("#xptxt").textContent = `${P.xp % 100} / 100 XP · totale ${P.xp}`;
  $("#badges").innerHTML = P.badge.map((id) => { const b = BADGE.find((x) => x.id === id); return b ? `<i class="ti ti-${b.icona}" title="${esc(b.nome)}"></i>` : ""; }).join("");
}

// ---------- API ----------
async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (r.status === 401) { location.href = "/login?torna=" + encodeURIComponent(location.pathname); throw new Error("Accesso richiesto"); }
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) { /* */ } throw new Error(typeof m === "string" ? m : JSON.stringify(m)); }
  return r.json();
}

// ---------- navigazione ----------
function vai(v) {
  $$("#nav button").forEach((b) => b.classList.toggle("on", b.dataset.v === v));
  $$(".view").forEach((s) => s.classList.toggle("on", s.id === "v-" + v));
  if (v === "mondo") disegnaMappa($("#mappa"), "persona");
  if (v === "dialoga") disegnaChatPersonas();
  if (v === "missioni") disegnaMissioni();
  if (v === "importa" && fonte.tipo === "ls") caricaSondaggi();
  window.scrollTo(0, 0);
}
$$("#nav button").forEach((b) => (b.onclick = () => vai(b.dataset.v)));
document.addEventListener("click", (e) => { const g = e.target.closest("[data-go]"); if (g) vai(g.dataset.go); });

// ---------- mondo ----------
const personaById = (id) => S.mondo.personas.find((p) => p.id === id);
function compScalata() {
  const tot = Object.values(S.comp).reduce((a, m) => a + Object.values(m).reduce((x, y) => x + y, 0), 0) || 1;
  const k = Math.min(1, 400 / tot), out = {};
  for (const [u, mix] of Object.entries(S.comp)) { out[u] = {}; for (const [p, n] of Object.entries(mix)) out[u][p] = Math.max(0, Math.round(n * k)); }
  return out;
}
function posUnita(u) { return [60 + (u.x ?? 50) / 100 * 880, 50 + (u.y ?? 50) / 100 * 440]; }
function rngSeed(s) { let x = s * 9301 + 49297; return () => ((x = (x * 9301 + 49297) % 233280) / 233280); }

function disegnaMappa(svg, modo, statoUnita) {
  if (!S.mondo) return;
  const comp = compScalata();
  const unita = S.mondo.unita.map((u, i) => ({ ...u, x: u.x ?? 15 + 70 * (i / Math.max(1, S.mondo.unita.length - 1)), y: u.y ?? 50 }));
  let h = "";
  // strade tra le unità più vicine
  const pts = unita.map(posUnita);
  const fatte = new Set();
  pts.forEach((p, i) => {
    pts.map((q, j) => [j, Math.hypot(p[0] - q[0], p[1] - q[1])]).filter(([j]) => j !== i).sort((a, b) => a[1] - b[1]).slice(0, 2).forEach(([j]) => {
      const key = [i, j].sort().join("-"); if (fatte.has(key)) return; fatte.add(key);
      h += `<line x1="${p[0]}" y1="${p[1]}" x2="${pts[j][0]}" y2="${pts[j][1]}" stroke="#dfe3ea" stroke-width="10" stroke-linecap="round"/>`;
      h += `<line x1="${p[0]}" y1="${p[1]}" x2="${pts[j][0]}" y2="${pts[j][1]}" stroke="#fff" stroke-width="2" stroke-dasharray="8 8"/>`;
    });
  });
  unita.forEach((u, i) => {
    const [cx, cy] = pts[i];
    const mix = comp[u.id] || {};
    let colori = [];
    let n = Object.values(mix).reduce((a, b) => a + b, 0);
    if (modo === "persona") {
      for (const [pid, c] of Object.entries(mix)) { const p = personaById(pid); for (let k = 0; k < c; k++) colori.push({ fill: p ? p.colore : "#999" }); }
    } else {
      const st = (statoUnita || {})[u.id] || { pos: 0, neu: 0, neg: 0, non: n };
      n = st.pos + st.neu + st.neg + st.non;
      colori = [...Array(st.pos).fill({ fill: POS }), ...Array(st.neu).fill({ fill: NEU }), ...Array(st.neg).fill({ fill: NEG }), ...Array(st.non).fill({ fill: "none", stroke: "#a3a9b5" })];
    }
    const rnd = rngSeed(i + 3);
    for (let k = colori.length - 1; k > 0; k--) { const j = Math.floor(rnd() * (k + 1)); [colori[k], colori[j]] = [colori[j], colori[k]]; }
    const R = 22 + Math.sqrt(n) * 4.6;
    let tinta = "#f2f4f8";
    if (modo !== "persona" && statoUnita && statoUnita[u.id] && statoUnita[u.id].indice != null) {
      const v = statoUnita[u.id].indice; tinta = v >= 55 ? "#e3f7ee" : v <= 45 ? "#fdeaea" : "#f2f4f8";
    }
    h += `<circle cx="${cx}" cy="${cy}" r="${R}" fill="${tinta}" stroke="#d7dce5"/>`;
    colori.forEach((c, k) => {
      const a = k * 2.39996, r = 4.4 * Math.sqrt(k + 0.5);
      h += `<circle cx="${(cx + r * Math.cos(a)).toFixed(1)}" cy="${(cy + r * Math.sin(a)).toFixed(1)}" r="3.4" fill="${c.fill}" ${c.stroke ? `stroke="${c.stroke}" stroke-width="1"` : ""}/>`;
    });
    const etich = esc(u.nome) + (modo !== "persona" && statoUnita && statoUnita[u.id] && statoUnita[u.id].indice != null ? ` · ${f0(statoUnita[u.id].indice)}` : ` · ${n}`);
    h += `<text x="${cx}" y="${cy + R + 18}" text-anchor="middle" font-size="19" font-weight="600" fill="#16202e">${etich}</text>`;
  });
  svg.innerHTML = h;
}

function disegnaComposizione() {
  const m = S.mondo;
  $("#etichetta-unita").textContent = (m.etichetta_unita || "unità").toLowerCase();
  if (!S.unita || !S.comp[S.unita]) S.unita = m.unita[0].id;
  $("#unita-chips").innerHTML = m.unita.map((u) => `<button class="chip ${u.id === S.unita ? "on" : ""}" data-u="${u.id}">${esc(u.nome)}</button>`).join("");
  $$("#unita-chips button").forEach((b) => (b.onclick = () => { S.unita = b.dataset.u; disegnaComposizione(); }));
  const mix = S.comp[S.unita] || {};
  $("#sliders").innerHTML = m.personas.map((p) => `<div class="sl"><span class="av" style="background:${p.colore}">${esc(p.avatar || "")}</span><span>${esc(p.nome)}</span><input type="range" min="0" max="80" value="${mix[p.id] || 0}" data-p="${p.id}"><b>${mix[p.id] || 0}</b></div>`).join("");
  $$("#sliders input").forEach((inp) => (inp.oninput = () => {
    S.comp[S.unita][inp.dataset.p] = +inp.value; inp.nextElementSibling.textContent = inp.value;
    P.compModificata = true; salva(); totPop(); disegnaMappa($("#mappa"), "persona");
  }));
  totPop();
}
function totPop() { const t = Object.values(S.comp).reduce((a, m) => a + Object.values(m).reduce((x, y) => x + y, 0), 0); $("#tot-pop").textContent = `${t} persone in totale`; }
$("#reset-comp").onclick = () => { S.comp = JSON.parse(JSON.stringify(S.mondo.composizione)); disegnaComposizione(); disegnaMappa($("#mappa"), "persona"); };

function disegnaPersonas() {
  const comp = S.comp, tot = {};
  let T = 0;
  for (const mix of Object.values(comp)) for (const [p, n] of Object.entries(mix)) { tot[p] = (tot[p] || 0) + n; T += n; }
  const nomiCan = Object.fromEntries(S.mondo.canali.map((c) => [c.id, c.nome])); nomiCan.passaparola = "passaparola";
  const barra = (lab, v, col) => `<div class="stat"><span>${lab}</span><div class="bar"><div style="width:${Math.round(v * 100)}%;background:${col}"></div></div><span>${Math.round(v * 100)}</span></div>`;
  $("#personas-cards").innerHTML = S.mondo.personas.map((p) => `
    <div class="card pcard" data-p="${p.id}">
      <div class="ph"><span class="bigav" style="background:${p.colore}">${esc(p.avatar || "")}</span><div><b>${esc(p.nome)}</b><small>${esc(p.categoria || "")} · ${T ? Math.round(100 * (tot[p.id] || 0) / T) : 0}% della popolazione</small></div></div>
      <p class="muted" style="margin:0 0 8px">${esc(p.descrizione || "")}</p>
      ${barra("Atteggiamento", (p.atteggiamento + 1) / 2, p.atteggiamento >= 0 ? POS : NEG)}
      ${barra("Fiducia", p.fiducia, "#3b5bfd")}${barra("Scetticismo", p.scetticismo, "#f4a261")}${barra("Influenza", p.influenza, "#8f5bff")}
      ${(p.criticita || []).length ? `<div class="lab">Criticità</div><ul>${p.criticita.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}
      ${(p.aspettative || []).length ? `<div class="lab">Aspettative</div><ul>${p.aspettative.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}
      <div class="lab">Si fida di</div>${Object.entries(p.canali || {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => `<span class="tag">${esc(nomiCan[k] || k)} ${Math.round(v * 100)}%</span>`).join("")}
    </div>`).join("");
  $$(".pcard").forEach((c) => (c.onclick = () => { S.chatP = c.dataset.p; vai("dialoga"); }));
}

// ---------- lancia ----------
function stimaCanale(cid) {
  let s = 0, n = 0;
  for (const mix of Object.values(S.comp)) for (const [pid, c] of Object.entries(mix)) { const p = personaById(pid); if (p) { s += c * (0.05 + 0.9 * (p.canali?.[cid] ?? 0.4)); n += c; } }
  return n ? (100 * s) / n : 0;
}
function disegnaLancia() {
  const m = S.mondo;
  if (!S.canale || !m.canali.find((c) => c.id === S.canale)) S.canale = m.canali[0].id;
  $("#canali").innerHTML = m.canali.map((c) => `<button class="canale ${c.id === S.canale ? "on" : ""}" data-c="${c.id}"><i class="ti ti-${esc(c.icona || "speakerphone")}"></i><b>${esc(c.nome)}</b><small>raggiunge subito circa il ${f0(stimaCanale(c.id))}%</small></button>`).join("");
  $$("#canali button").forEach((b) => (b.onclick = () => { S.canale = b.dataset.c; disegnaLancia(); }));
  $("#esempi").innerHTML = (m.esempi || []).map((e, i) => `<button class="chip" data-i="${i}">${esc(e.titolo)}</button>`).join("");
  $$("#esempi button").forEach((b) => (b.onclick = () => { const e = m.esempi[+b.dataset.i]; $("#msg").value = e.testo; S.canale = e.canale; disegnaLancia(); radiografia(); }));
  $("#bersaglio").innerHTML = m.unita.map((u) => `<button class="chip ${S.bersaglio.has(u.id) ? "on" : ""}" data-u="${u.id}">${esc(u.nome)}</button>`).join("");
  $$("#bersaglio button").forEach((b) => (b.onclick = () => { S.bersaglio.has(b.dataset.u) ? S.bersaglio.delete(b.dataset.u) : S.bersaglio.add(b.dataset.u); disegnaLancia(); }));
  const sel = m.canali.map((c) => `<option value="${c.id}">${esc(c.nome)}</option>`).join("");
  const va = $("#a-can").value, vb = $("#b-can").value;
  $("#a-can").innerHTML = sel; $("#b-can").innerHTML = sel;
  if (m.canali.some((c) => c.id === va)) $("#a-can").value = va;
  if (m.canali.some((c) => c.id === vb)) $("#b-can").value = vb;
  if (m.esempi?.length > 1) { if (!$("#a-msg").value) { $("#a-msg").value = m.esempi[0].testo; $("#a-can").value = m.esempi[0].canale; } if (!$("#b-msg").value) { $("#b-msg").value = m.esempi[1].testo; $("#b-can").value = m.esempi[1].canale; } }
}
["round", "esec"].forEach((id) => ($("#" + id).oninput = () => ($("#" + id + "-v").textContent = $("#" + id).value)));

let tRadio;
$("#msg").addEventListener("input", () => { clearTimeout(tRadio); tRadio = setTimeout(radiografia, 350); });
async function radiografia() {
  const t = $("#msg").value.trim();
  if (t.length < 3) { $("#radiografia").innerHTML = `<p class="muted">Scrivi almeno qualche parola.</p>`; return; }
  const a = await api("/api/analizza", { messaggio: t });
  const temi = Object.values(a.temi);
  const m = (lab, v, nota) => `<div class="meter"><span>${lab}<b>${Math.round(v * 100)}</b></span><div class="bar"><div style="width:${Math.round(v * 100)}%"></div></div>${nota ? `<small class="muted">${nota}</small>` : ""}</div>`;
  $("#radiografia").innerHTML = `
    <div class="lab">Temi toccati</div>
    ${temi.length ? temi.map((x) => `<span class="tema ${x.verso > 0.15 ? "p" : x.verso < -0.15 ? "n" : "z"}"><i class="ti ti-${x.verso > 0.15 ? "trending-up" : x.verso < -0.15 ? "trending-down" : "minus"}"></i>${esc(x.nome)}</span>`).join("") : `<p class="muted">Nessun tema riconosciuto.</p>`}
    ${m("Concretezza", a.concretezza, "date, numeri, chi fa cosa")}
    ${m("Ascolto", a.ascolto, "spazio per proposte e confronto")}
    ${m("Enfasi", a.enfasi, "superlativi: irritano gli scettici")}
    ${m("Incertezza", a.incertezza, "condizionali e ipotesi")}
    <p class="muted">${a.parole} parole</p>`;
}

$("#lancia").onclick = async () => {
  const t = $("#msg").value.trim();
  $("#lancia-err").textContent = "";
  if (t.length < 3) { $("#lancia-err").textContent = "Scrivi il messaggio da lanciare."; return; }
  $("#lancia").disabled = true; $("#lancia").innerHTML = `<i class="ti ti-loader-2"></i> Simulazione in corso…`;
  try {
    const r = await simula(t, S.canale, 7);
    S.ris = r;
    mostraRisultati(r, true);
    vai("risultati");
    avviaPlay();
  } catch (e) { $("#lancia-err").textContent = "Simulazione non riuscita: " + e.message; }
  finally { $("#lancia").disabled = false; $("#lancia").innerHTML = `<i class="ti ti-rocket"></i> Lancia la simulazione`; }
};
function simula(testo, canale, seme) {
  return api("/api/simula", { mondo_id: S.mondo.id, messaggio: testo, canale, unita_bersaglio: [...S.bersaglio], composizione: S.comp,
    round: +$("#round").value, esecuzioni: +$("#esec").value, seme, usa_llm: $("#usa-llm").checked });
}

// ---------- risultati ----------
function mostraRisultati(r, premia) {
  $("#ris-vuoto").hidden = true; $("#ris").hidden = false;
  $("#ris-sotto").textContent = `«${r.messaggio.slice(0, 120)}${r.messaggio.length > 120 ? "…" : ""}» · ${r.canale.nome} · ${r.esecuzioni} esecuzioni · modalità ${r.modalita}`;
  const fin = r.finale;
  const g = $("#g-val"), L = g.getTotalLength();
  g.style.strokeDasharray = L; g.style.strokeDashoffset = L;
  requestAnimationFrame(() => { g.style.strokeDashoffset = L * (1 - fin.indice / 100); g.style.stroke = fin.indice >= 55 ? POS : fin.indice <= 45 ? NEG : "#f2b705"; });
  animaNumero($("#indice"), fin.indice);
  $("#stelle").innerHTML = [1, 2, 3].map((i) => `<span class="${i <= r.stelle ? "on" : ""}" style="animation-delay:${i * 0.25}s">★</span>`).join("");
  $("#xp-gain").textContent = premia ? `+${r.xp} XP` : "";
  $("#k-canale").textContent = f0(fin.raggiunti_canale) + "%";
  $("#k-inf").textContent = f0(fin.informati) + "%";
  $("#k-pos").textContent = f0(fin.positivi) + "%";
  $("#k-neg").textContent = f0(fin.negativi) + "%";
  $("#k-stab").textContent = fin.stabilita;
  $("#k-ag").textContent = r.agenti;
  $("#t").max = r.unita.length - 1; $("#t").value = r.unita.length - 1;
  frame(r.unita.length - 1);
  grafico(r);
  $("#classifica").innerHTML = r.personas.map((p, i) => {
    const v = p.indice ?? 50, a = Math.min(v, p.partenza), b = Math.max(v, p.partenza);
    const col = v >= 55 ? POS : v <= 45 ? NEG : "#f2b705";
    return `<div class="rank" title="${esc(p.nome)}: da ${f0(p.partenza)} a ${f0(v)}"><span class="av" style="background:${p.colore}">${i + 1}</span><span>${esc(p.nome)}</span>
      <div class="track"><div class="fill" style="left:${a}%;width:${Math.max(1, b - a)}%;background:${col}"></div><div class="mark" style="left:${p.partenza}%"></div></div><b>${f0(v)}</b></div>`;
  }).join("");
  $("#obiezioni").innerHTML = r.obiezioni.length ? r.obiezioni.map((o) => `<div class="ob">${esc(o.testo)} <span class="muted">${o.quota}%</span><div class="bar" style="width:${o.quota}%"></div></div>`).join("") : `<p class="muted">Nessuna obiezione rilevante.</p>`;
  $("#voci").innerHTML = r.voci.length ? r.voci.map((v) => `<div class="voce"><i class="ti ti-ear"></i>${esc(v)}</div>`).join("") : `<p class="muted">Nessuna voce negativa rilevante nel passaparola.</p>`;
  $("#frasi").innerHTML = r.frasi.map((q) => { const p = personaById(q.persona_id) || {}; return `<div class="quote ${q.tono}"><span class="av" style="background:${p.colore || "#888"};width:30px;height:30px">${esc(p.avatar || "")}</span><div class="bub"><small>${esc(q.persona)} · profilo simulato</small>${esc(q.testo)}</div></div>`; }).join("");
  $("#consigli").innerHTML = r.consigli.map((c) => `<div class="tip"><i class="ti ti-bulb"></i><span>${esc(c)}</span></div>`).join("");
  $("#avvertenza").textContent = r.avvertenza + (r.errore_llm ? " Il modello linguistico non ha risposto: usate le regole." : "");
  if (premia) premi(r);
}
function animaNumero(el, fine) { const t0 = performance.now(); const step = (t) => { const k = Math.min(1, (t - t0) / 900); el.textContent = f0(fine * k); if (k < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); }
function frame(t) { $("#t-lab").textContent = t === 0 ? "Annuncio" : `Round ${t}`; disegnaMappa($("#mappa-ris"), "sentiment", S.ris.unita[t]); }
$("#t").oninput = () => frame(+$("#t").value);
let playT;
function avviaPlay() {
  clearInterval(playT); let t = 0; $("#t").value = 0; frame(0);
  $("#play").innerHTML = `<i class="ti ti-player-pause"></i>`;
  playT = setInterval(() => { t++; if (t >= S.ris.unita.length) { clearInterval(playT); playT = null; $("#play").innerHTML = `<i class="ti ti-player-play"></i>`; return; } $("#t").value = t; frame(t); }, 650);
}
$("#play").onclick = () => { if (playT) { clearInterval(playT); playT = null; $("#play").innerHTML = `<i class="ti ti-player-play"></i>`; } else avviaPlay(); };

function grafico(r) {
  const W = 520, H = 260, l = 40, rt = 14, t = 14, b = 34, n = r.serie.indice.media.length;
  const x = (i) => l + (i * (W - l - rt)) / Math.max(1, n - 1), y = (v) => t + (1 - v / 100) * (H - t - b);
  let h = "";
  [0, 25, 50, 75, 100].forEach((v) => (h += `<line x1="${l}" x2="${W - rt}" y1="${y(v)}" y2="${y(v)}" stroke="#eef0f4"/><text x="${l - 8}" y="${y(v) + 4}" font-size="11" text-anchor="end" fill="#8a91a0">${v}</text>`));
  h += `<line x1="${l}" x2="${W - rt}" y1="${y(50)}" y2="${y(50)}" stroke="#c9ced8" stroke-dasharray="3 3"/>`;
  const S2 = r.serie.indice;
  const band = S2.max.map((v, i) => `${x(i)},${y(v)}`).join(" ") + " " + S2.min.map((v, i) => `${x(i)},${y(v)}`).reverse().join(" ");
  h += `<polygon points="${band}" fill="rgba(59,91,253,.14)"/>`;
  h += `<polyline points="${r.serie.informati.media.map((v, i) => `${x(i)},${y(v)}`).join(" ")}" fill="none" stroke="#9aa1ae" stroke-width="2" stroke-dasharray="5 4"/>`;
  h += `<polyline points="${S2.media.map((v, i) => `${x(i)},${y(v)}`).join(" ")}" fill="none" stroke="#3b5bfd" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>`;
  S2.media.forEach((v, i) => (h += `<circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="#3b5bfd" stroke="#fff" stroke-width="1.5"><title>Round ${i}: gradimento ${f1(v)}, informati ${f1(r.serie.informati.media[i])}%</title></circle>`));
  for (let i = 0; i < n; i++) h += `<text x="${x(i)}" y="${H - 14}" font-size="11" text-anchor="middle" fill="#8a91a0">${i}</text>`;
  h += `<text x="${(W + l) / 2}" y="${H - 1}" font-size="11" text-anchor="middle" fill="#8a91a0">round</text>`;
  $("#grafico").innerHTML = h;
}

function premi(r) {
  aggiungiXp(r.xp, `${r.stelle} ${r.stelle === 1 ? "stella" : "stelle"}`);
  badge("primo");
  if (r.stelle === 3) badge("tre-stelle");
  if (P.compModificata) badge("costruttore");
  const fatte = [];
  for (const m of S.mondo.missioni || []) {
    const key = S.mondo.id + ":" + m.id;
    if (P.missioni[key]) continue;
    if (missioneOk(m.condizione, r)) { P.missioni[key] = true; fatte.push(m); }
  }
  salva();
  $("#missioni-ok").innerHTML = fatte.map((m) => `<div class="mission-done"><i class="ti ti-target-arrow"></i><div><b>Missione compiuta: ${esc(m.titolo)}</b><br><span class="muted">+${m.xp} XP</span></div></div>`).join("");
  fatte.forEach((m) => aggiungiXp(m.xp, "missione " + m.titolo));
  if (fatte.length) badge("missione");
}
function missioneOk(c, r) {
  const ip = (id) => (r.personas.find((p) => p.id === id) || {}).indice ?? 0;
  switch (c.tipo) {
    case "indice_personas_min": return c.personas.every((id) => ip(id) >= c.valore);
    case "indice_e_negativi": return r.finale.indice >= c.indice && r.finale.negativi < c.negativi;
    case "informati_min": return r.finale.informati >= c.valore;
    case "nessuna_voce_con_tema": return !!r.analisi.temi[c.tema] && r.voci.length === 0;
    case "indice_min_con_tema": return !!r.analisi.temi[c.tema] && r.finale.indice >= c.valore;
    default: return false;
  }
}

// ---------- dialoga ----------
const DOMANDE = ["Qual è il problema principale per te?", "Che cosa ti manca per stare meglio?", "Come preferisci essere informato?", "Cosa pensi dell'ultimo annuncio?", "Cosa ti farebbe cambiare idea?"];
function disegnaChatPersonas() {
  if (!S.chatP || !personaById(S.chatP)) S.chatP = S.mondo.personas[0].id;
  $("#chat-personas").innerHTML = S.mondo.personas.map((p) => `<button class="${p.id === S.chatP ? "on" : ""}" data-p="${p.id}"><span class="av" style="background:${p.colore}">${esc(p.avatar || "")}</span>${esc(p.nome)}</button>`).join("");
  $$("#chat-personas button").forEach((b) => (b.onclick = () => { S.chatP = b.dataset.p; disegnaChatPersonas(); }));
  const p = personaById(S.chatP);
  $("#chat-head").innerHTML = `<span class="bigav" style="background:${p.colore};width:42px;height:42px;border-radius:12px;color:#fff;display:grid;place-items:center;font-weight:800">${esc(p.avatar || "")}</span><div><b>${esc(p.nome)}</b><br><small class="muted">${esc(p.categoria || "")} · profilo simulato da dati aggregati</small></div>`;
  $("#domande").innerHTML = DOMANDE.map((d) => `<button class="chip">${esc(d)}</button>`).join("");
  $$("#domande button").forEach((b) => (b.onclick = () => chiedi(b.textContent)));
  disegnaMsgs();
}
function disegnaMsgs() {
  const st = S.chat[S.mondo.id + ":" + S.chatP] || [];
  $("#msgs").innerHTML = st.length ? st.map((m) => `<div class="m ${m.role === "user" ? "u" : "a"}">${m.role === "assistant" ? `<small>${esc(personaById(S.chatP).nome)}</small>` : ""}${esc(m.content)}</div>`).join("") : `<p class="muted">Inizia con una domanda, o scegline una qui sotto.</p>`;
  $("#msgs").scrollTop = 1e6;
}
async function chiedi(testo) {
  testo = testo.trim(); $("#chat-err").textContent = "";
  if (!testo) { $("#chat-err").textContent = "Scrivi una domanda."; return; }
  const k = S.mondo.id + ":" + S.chatP; const st = (S.chat[k] = S.chat[k] || []);
  st.push({ role: "user", content: testo }); disegnaMsgs();
  try {
    const r = await api("/api/chat", { mondo_id: S.mondo.id, persona_id: S.chatP, domanda: testo, storia: st.slice(0, -1), contesto_messaggio: $("#ctx").checked && S.ris ? S.ris.messaggio : null, usa_llm: true });
    st.push({ role: "assistant", content: r.risposta }); disegnaMsgs();
    P.domande++; salva(); aggiungiXp(2); if (P.domande >= 5) badge("ascoltatore");
  } catch (e) { $("#chat-err").textContent = "Risposta non riuscita: " + e.message; }
}
$("#chat-form").onsubmit = (e) => { e.preventDefault(); const v = $("#chat-in").value; $("#chat-in").value = ""; chiedi(v); };

// ---------- sfida ----------
$("#sfida-go").onclick = async () => {
  const a = $("#a-msg").value.trim(), b = $("#b-msg").value.trim();
  $("#sfida-err").textContent = "";
  if (a.length < 3 || b.length < 3) { $("#sfida-err").textContent = "Scrivi entrambe le versioni."; return; }
  $("#sfida-go").disabled = true; $("#sfida-ris").innerHTML = `<p class="muted">Simulazione delle due versioni…</p>`;
  try {
    const [ra, rb] = await Promise.all([simula(a, $("#a-can").value, 11), simula(b, $("#b-can").value, 11)]);
    const win = ra.finale.indice >= rb.finale.indice ? "A" : "B";
    const cell = (r, lab) => `<div class="card side-res ${win === lab ? "win" : ""}">${win === lab ? `<i class="ti ti-crown crown"></i>` : ""}<h3 style="justify-content:center">Versione ${lab}</h3><b>${f0(r.finale.indice)}</b><span class="muted">gradimento</span>
      <div class="stars">${[1, 2, 3].map((i) => `<span class="${i <= r.stelle ? "on" : ""}">★</span>`).join("")}</div>
      <p class="muted">Positivi ${f0(r.finale.positivi)}% · negativi ${f0(r.finale.negativi)}% · raggiunti dal canale ${f0(r.finale.raggiunti_canale)}%</p></div>`;
    const diff = ra.personas.map((p) => { const q = rb.personas.find((x) => x.id === p.id) || {}; return { nome: p.nome, a: p.indice ?? 50, b: q.indice ?? 50 }; }).sort((x, y) => Math.abs(y.b - y.a) - Math.abs(x.b - x.a)).slice(0, 6);
    $("#sfida-ris").innerHTML = `<div class="vs">${cell(ra, "A")}<div class="vsx">VS</div>${cell(rb, "B")}</div>
      <div class="card mt"><h3><i class="ti ti-arrows-diff"></i> Dove cambia di più</h3>${diff.map((d) => `<div class="rank"><span></span><span>${esc(d.nome)}</span><div class="track"><div class="fill" style="left:${Math.min(d.a, d.b)}%;width:${Math.max(1, Math.abs(d.b - d.a))}%;background:${d.b > d.a ? POS : NEG}"></div><div class="mark" style="left:${d.a}%"></div></div><b>${d.b - d.a >= 0 ? "+" : ""}${f0(d.b - d.a)}</b></div>`).join("")}<p class="hint">La tacca è la versione A, la barra mostra lo spostamento verso la versione B.</p></div>`;
    S.ris = win === "A" ? ra : rb; mostraRisultati(S.ris, false);
    aggiungiXp(15, "sfida completata"); badge("stratega");
  } catch (e) { $("#sfida-err").textContent = "Sfida non riuscita: " + e.message; $("#sfida-ris").innerHTML = ""; }
  finally { $("#sfida-go").disabled = false; }
};

// ---------- missioni ----------
function disegnaMissioni() {
  const ms = S.mondo?.missioni || [];
  $("#missioni").innerHTML = ms.length ? ms.map((m) => { const ok = P.missioni[S.mondo.id + ":" + m.id]; return `<div class="card mcard ${ok ? "done" : ""}"><h3><i class="ti ti-${ok ? "circle-check" : "target-arrow"}"></i> ${esc(m.titolo)}</h3><p>${esc(m.descrizione)}</p><span class="xp">${m.xp} XP</span> ${ok ? `<span class="tag">completata</span>` : `<button class="ghost" data-go="lancia" style="float:right">Prova</button>`}</div>`; }).join("") : `<p class="muted">Questo mondo non ha missioni.</p>`;
  $("#badge-list").innerHTML = BADGE.map((b) => `<div class="card ${P.badge.includes(b.id) ? "got" : ""}"><i class="ti ti-${b.icona}"></i><h3 style="justify-content:center">${esc(b.nome)}</h3><p class="muted">${esc(b.desc)}</p></div>`).join("");
}

// ---------- importa ----------
let csvTesto = "", fonte = { tipo: "ls" }, lsSondaggi = null;
$$("#imp-fonte button").forEach((b) => (b.onclick = () => {
  $$("#imp-fonte button").forEach((x) => x.classList.toggle("on", x === b));
  fonte = { tipo: b.dataset.f }; $("#imp-ls").hidden = b.dataset.f !== "ls"; $("#imp-file").hidden = b.dataset.f !== "file";
  $("#imp-cfg").hidden = true; $("#imp-info").textContent = ""; $("#imp-err").textContent = "";
  if (b.dataset.f === "ls") caricaSondaggi();
}));
async function caricaSondaggi(forza) {
  if (lsSondaggi && !forza) return disegnaSondaggi();
  $("#ls-lista").innerHTML = `<p class="muted">Collegamento a LimeSurvey…</p>`;
  try {
    const st = await api("/api/limesurvey/stato");
    if (!st.configurato) { $("#ls-lista").innerHTML = `<p class="muted">Il collegamento a LimeSurvey non è ancora configurato. ${$("#link-admin").hidden ? "Chiedi a chi gestisce l'area riservata di inserire indirizzo, utente e password." : `Inseriscilo nell'<a href="/admin">area riservata</a>.`}</p>`; return; }
    lsSondaggi = await api("/api/limesurvey/sondaggi"); disegnaSondaggi();
  } catch (e) { $("#ls-lista").innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
function disegnaSondaggi() {
  if (!lsSondaggi.length) { $("#ls-lista").innerHTML = `<p class="muted">Nessun sondaggio trovato per questo utente.</p>`; return; }
  $("#ls-lista").innerHTML = lsSondaggi.map((s) => `<div class="rank" style="grid-template-columns:minmax(0,1fr) 110px 120px 110px"><span><b>${esc(s.titolo)}</b><br><small class="muted">ID ${esc(s.sid)}</small></span>
    <span class="tag">${s.attivo ? "attivo" : "non attivo"}</span><span class="muted">${s.completate == null ? "" : s.completate + " risposte complete"}</span>
    <button data-sid="${esc(s.sid)}"><i class="ti ti-arrow-right"></i> Usa</button></div>`).join("");
  $$("#ls-lista button[data-sid]").forEach((b) => (b.onclick = () => anteprimaLs(b.dataset.sid)));
}
$("#ls-aggiorna").onclick = () => caricaSondaggi(true);
async function anteprimaLs(sid) {
  $("#imp-err").textContent = ""; $("#imp-info").textContent = "Scarico le risposte…";
  const s = lsSondaggi.find((x) => x.sid === sid) || { titolo: sid };
  try {
    const a = await api("/api/limesurvey/anteprima", { sid });
    fonte = { tipo: "ls", sid, titolo: s.titolo };
    $("#imp-nome").value = s.titolo;
    configuraImport(a, `Sondaggio: ${s.titolo}`, `${a.righe} risposte complete. Le risposte restano in memoria sul server solo per il calcolo delle medie e non vengono salvate.`);
  } catch (e) { $("#imp-info").textContent = ""; $("#imp-err").textContent = e.message; }
}
function configuraImport(a, titolo, info) {
  const et = a.etichette || {};
  const lab = (c) => (et[c] ? `${c} · ${et[c].slice(0, 70)}` : c);
  $("#imp-titolo").textContent = titolo; $("#imp-info").textContent = info;
  const opt = (cols, vuota) => (vuota ? `<option value="">— nessuna —</option>` : "") + cols.map((c) => `<option value="${esc(c)}">${esc(lab(c))}</option>`).join("");
  $("#imp-gruppo").innerHTML = opt(a.categoriche.length ? a.categoriche : a.colonne);
  $("#imp-fid").innerHTML = opt(a.numeriche, true);
  const fid = a.numeriche.find((c) => /fiduc/i.test(c + " " + (et[c] || "")));
  if (fid) $("#imp-fid").value = fid;
  $("#imp-modello").innerHTML = S.mondi.map((m) => `<option value="${m.id}">${esc(m.nome)}</option>`).join("");
  $("#imp-modello").value = S.mondo?.id || S.mondi[0].id;
  $("#imp-clima").innerHTML = a.numeriche.map((c) => `<button class="chip ${c === fid ? "" : "on"}" data-c="${esc(c)}" title="${esc(et[c] || c)}">${esc(lab(c).slice(0, 60))}</button>`).join("") || `<p class="muted">Nessuna domanda numerica trovata.</p>`;
  $$("#imp-clima button").forEach((b) => (b.onclick = () => b.classList.toggle("on")));
  $("#imp-cfg").hidden = false;
}
$("#file").onchange = async (e) => {
  const f = e.target.files[0]; $("#imp-err").textContent = ""; if (!f) return;
  csvTesto = await f.text();
  try {
    const a = await api("/api/importa/anteprima", { csv: csvTesto });
    fonte = { tipo: "file" };
    configuraImport(a, "File: " + f.name, `${a.righe} risposte, ${a.colonne.length} colonne. Al server arrivano solo i dati per calcolare le medie, che non vengono salvati.`);
  } catch (err) { $("#imp-err").textContent = "File non leggibile: " + err.message; }
};
$("#imp-go").onclick = async () => {
  $("#imp-err").textContent = "";
  const comune = { nome: $("#imp-nome").value || "Indagine reale", colonna_gruppo: $("#imp-gruppo").value,
    colonne_clima: $$("#imp-clima button.on").map((b) => b.dataset.c), colonna_fiducia: $("#imp-fid").value || null, modello_id: $("#imp-modello").value };
  if (!comune.colonne_clima.length) { $("#imp-err").textContent = "Scegli almeno una domanda di clima o soddisfazione."; return; }
  $("#imp-go").disabled = true;
  try {
    const r = fonte.tipo === "ls" ? await api("/api/limesurvey/importa", { ...comune, sid: fonte.sid, titolo: fonte.titolo })
      : await api("/api/importa", { ...comune, csv: csvTesto });
    toast(`<i class="ti ti-check"></i> Mondo creato con ${r.personas} personas`);
    badge("analista");
    await caricaMondi(r.id);
    vai("personas");
  } catch (e) { $("#imp-err").textContent = e.message; }
  finally { $("#imp-go").disabled = false; }
};

// ---------- avvio ----------
async function caricaMondo(id) {
  S.mondo = await api("/api/mondi/" + id);
  S.comp = JSON.parse(JSON.stringify(S.mondo.composizione));
  S.unita = null; S.bersaglio = new Set(); S.ris = null;
  $("#mondo-nome").textContent = S.mondo.nome; $("#mondo-desc").textContent = S.mondo.descrizione || "";
  $("#legenda-personas").innerHTML = S.mondo.personas.map((p) => `<span><i class="dot" style="background:${p.colore}"></i>${esc(p.nome)}</span>`).join("");
  $("#ris-vuoto").hidden = false; $("#ris").hidden = true; $("#ris-sotto").textContent = "Lancia un annuncio per vedere le reazioni.";
  $("#a-msg").value = ""; $("#b-msg").value = "";
  disegnaComposizione(); disegnaMappa($("#mappa"), "persona"); disegnaPersonas(); disegnaLancia(); disegnaMissioni();
  if (!$("#msg").value && S.mondo.esempi?.length) { $("#msg").value = S.mondo.esempi[0].testo; S.canale = S.mondo.esempi[0].canale; disegnaLancia(); }
  radiografia();
}
async function caricaMondi(sel) {
  S.mondi = await api("/api/mondi");
  $("#mondo").innerHTML = S.mondi.map((m) => `<option value="${m.id}">${esc(m.nome)}</option>`).join("");
  const id = sel || S.mondi[0].id; $("#mondo").value = id;
  await caricaMondo(id);
}
$("#esci").onclick = async () => { await fetch("/api/logout", { method: "POST" }); location.href = "/login"; };
$("#mondo").onchange = () => { $("#msg").value = ""; caricaMondo($("#mondo").value); };
(async () => {
  disegnaPlayer();
  try {
    const st = await api("/api/stato");
    S.llm = st.disponibile;
    $("#round").value = st.round; $("#round-v").textContent = st.round; $("#esec").value = st.esecuzioni; $("#esec-v").textContent = st.esecuzioni;
    $("#link-admin").hidden = st.ruolo !== "admin";
    $("#esci").hidden = !st.protezione;
    $("#modalita").textContent = st.disponibile ? `Modello linguistico: ${st.modello_linguistico}` : "Modalità dimostrativa (regole)";
    $("#modalita").classList.toggle("llm", st.disponibile);
    $("#usa-llm").checked = st.disponibile; $("#usa-llm").disabled = !st.disponibile;
    if (!st.disponibile) $("#usa-llm").parentElement.title = "Configura una chiave API nel file .env per usare il modello linguistico";
    await caricaMondi();
  } catch (e) { document.querySelector("main").innerHTML = `<div class="empty"><i class="ti ti-plug-connected-x"></i><p>Server non raggiungibile: ${esc(e.message)}</p></div>`; }
})();
