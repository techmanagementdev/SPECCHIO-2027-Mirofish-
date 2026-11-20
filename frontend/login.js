"use strict";
const q = new URLSearchParams(location.search);
const area = q.get("area") === "admin" ? "admin" : "utente";
let torna = q.get("torna") || (area === "admin" ? "/admin" : "/");
if (!torna.startsWith("/") || torna.startsWith("//")) torna = "/";
if (area === "admin") {
  document.getElementById("titolo").textContent = "Area riservata";
  document.getElementById("sotto").textContent = "Impostazioni di SPECCHIO";
  document.getElementById("switch").innerHTML = '<a href="/login">Vai all\'area visibile</a>';
} else {
  document.getElementById("switch").innerHTML = '<a href="/login?area=admin">Area riservata</a>';
}
document.getElementById("f").onsubmit = async (e) => {
  e.preventDefault();
  const err = document.getElementById("err"); err.textContent = "";
  const pw = document.getElementById("pw").value;
  if (!pw) { err.textContent = "Inserisci la password."; return; }
  const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: pw, area }) });
  if (r.ok) { location.href = torna + (torna.includes("?") ? "&" : "?") + "v=" + Date.now(); return; }
  let m = "Accesso non riuscito"; try { m = (await r.json()).detail || m; } catch (x) { /* */ }
  err.textContent = m;
};
