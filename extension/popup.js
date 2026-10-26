import { api, diffHtml, escapeHtml, pct } from "./api.js";

const $ = (id) => document.getElementById(id);

document.querySelectorAll("[data-open]").forEach((b) =>
  b.addEventListener("click", () => chrome.tabs.create({ url: chrome.runtime.getURL(`app.html#${b.dataset.open}`) }))
);

api.health()
  .then((h) => { $("health").className = "pill ok"; $("health").textContent = h.gnani_key_configured ? "ready" : "no key"; })
  .catch(() => { $("health").className = "pill bad"; $("health").textContent = "offline"; });

$("go").addEventListener("click", async () => {
  const text = $("q").value.trim();
  if (!text) return;
  $("go").disabled = true;
  $("st").textContent = "Testing…";
  $("out").innerHTML = "";
  try {
    const r = await api.testText([text], "Asmita");
    const [clean, noisy] = Object.keys(r.conditions);
    const row = r.rows[0];
    const line = (cond, s) => `<div class="hyp"><span class="tag ${s === "F0" ? "f0" : "f3"}">${cond} ${s}</span>
      <span class="cer">CER ${pct(row[`${cond}_${s}_cer`])}</span><div class="diff">${diffHtml(text, row[`${cond}_${s}`])}</div></div>`;
    $("out").innerHTML = `<div class="card">${line(clean, "F0")}${line(noisy, "F0")}${line(noisy, "F3")}
      <p class="status">${(r.stats.elapsed_ms / 1000).toFixed(1)} s · ${r.stats.new_api_calls} new API calls</p></div>`;
    $("st").textContent = "";
  } catch (e) {
    $("st").textContent = "";
    $("out").innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
  } finally {
    $("go").disabled = false;
  }
});
