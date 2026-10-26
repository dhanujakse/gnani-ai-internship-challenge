import { api, diffHtml, escapeHtml, getSettings, pct, saveSettings } from "./api.js";

const $ = (id) => document.getElementById(id);
const COND_LABEL = { C1: "Clean 16 kHz", C2: "Phone band 8 kHz", C3: "Phone + light noise", C4: "Phone + heavy noise" };

// ---------- tabs ----------
function showTab(name) {
  document.querySelectorAll("nav button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll("main section").forEach((s) => (s.hidden = s.id !== `tab-${name}`));
  if (name === "bench") loadBench();
}
document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

function showError(el, err) {
  $(el).innerHTML = err ? `<div class="error">${escapeHtml(err.message || err)}</div>` : "";
}

async function busy(button, statusId, label, fn) {
  button.disabled = true;
  $(statusId).textContent = label;
  try {
    return await fn();
  } finally {
    button.disabled = false;
  }
}

// ---------- health ----------
async function checkHealth() {
  const pill = $("health");
  try {
    const h = await api.health();
    pill.className = "pill ok";
    pill.textContent = h.gnani_key_configured ? `server ok · ${h.daily_calls_left} calls left today` : "server ok · no Gnani key";
    const sel = $("voice");
    if (!sel.options.length) {
      for (const v of h.voices) sel.add(new Option(v, v, v === "Asmita", v === "Asmita"));
    }
  } catch (e) {
    pill.className = "pill bad";
    pill.textContent = "server offline";
    pill.title = e.message;
    if (!$("voice").options.length) for (const v of ["Asmita", "Trisha", "Brinda", "Vedika", "Noopur"]) $("voice").add(new Option(v, v));
  }
}

// ---------- text test ----------
function condBlock(row, cond, reference) {
  const audio = row.audio?.[cond] ? `<audio controls src="${row.audio[cond]}"></audio>` : "";
  const line = (setting, cls) => `
    <div class="hyp"><span class="tag ${cls}">${setting}</span><span class="cer">CER ${pct(row[`${cond}_${setting}_cer`])}</span>
      <div class="diff">${diffHtml(reference, row[`${cond}_${setting}`])}</div></div>`;
  return `<div class="cond"><div class="name">${cond} · ${COND_LABEL[cond] || cond}</div>${audio}${line("F0", "f0")}${line("F3", "f3")}</div>`;
}

function renderText(res) {
  const [clean, noisy] = Object.keys(res.conditions);
  const o = res.overall_cer;
  const tiles = `
    <div class="tiles">
      <div class="tile"><div class="v">${pct(o[`${clean}_F0`])}</div><div class="k">CER · ${COND_LABEL[clean]} · raw</div></div>
      <div class="tile"><div class="v">${pct(o[`${noisy}_F0`])}</div><div class="k">CER · ${COND_LABEL[noisy]} · raw</div></div>
      <div class="tile"><div class="v">${pct(o[`${noisy}_F3`])}</div><div class="k">CER · ${COND_LABEL[noisy]} · with fix layer</div></div>
      <div class="tile"><div class="v">${(res.stats.elapsed_ms / 1000).toFixed(1)} s</div><div class="k">${res.stats.new_api_calls} new API calls · n=${res.n}</div></div>
    </div>`;
  const cards = res.rows
    .map((r, i) => `<div class="card"><h3 class="ta">${i + 1}. ${escapeHtml(r.sentence)}</h3>
      <div class="grid2">${condBlock(r, clean, r.sentence)}${condBlock(r, noisy, r.sentence)}</div></div>`)
    .join("");
  $("text-results").innerHTML = tiles + cards +
    `<p class="status">Struck red = missed or wrong word, underlined green = inserted. Tiny samples are noisy; this is a quick check, not a benchmark.</p>`;
}

$("run-text").addEventListener("click", () =>
  busy($("run-text"), "text-status", "Speaking and transcribing…", async () => {
    showError("text-error", null);
    const sentences = $("text-input").value.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!sentences.length) return showError("text-error", "Enter at least one Tamil sentence.");
    try {
      const res = await api.testText(sentences, $("voice").value);
      renderText(res);
      $("text-status").textContent = `Done in ${(res._roundTripMs / 1000).toFixed(1)} s`;
      checkHealth();
    } catch (e) {
      $("text-status").textContent = "";
      showError("text-error", e);
    }
  })
);

// ---------- voice test ----------
let recorder = null;
let chunks = [];
let voiceBlob = null;
let voiceName = "voice.webm";
let recTimer = null;

function setVoice(blob, name) {
  voiceBlob = blob;
  voiceName = name;
  $("voice-preview").src = URL.createObjectURL(blob);
  $("voice-preview").hidden = false;
  $("run-voice").disabled = false;
}

$("rec").addEventListener("click", async () => {
  showError("voice-error", null);
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false } });
  } catch {
    const inPanel = location.hash === "#devtools";
    return showError("voice-error", inPanel
      ? "The microphone is not available inside DevTools. Open the tester in a tab from the extension popup."
      : "Microphone permission was denied. Allow it for this extension and try again.");
  }
  chunks = [];
  recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    clearInterval(recTimer);
    $("rec").textContent = "● Record again";
    $("rec-state").textContent = "";
    setVoice(new Blob(chunks, { type: "audio/webm" }), "voice.webm");
  };
  recorder.start();
  const started = Date.now();
  $("rec").textContent = "■ Stop";
  recTimer = setInterval(() => {
    const s = Math.floor((Date.now() - started) / 1000);
    $("rec-state").innerHTML = `<span class="rec"><span class="dot"></span>${s} s</span>`;
    if (s >= 30) recorder.stop();
  }, 250);
});

$("voice-file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (f) setVoice(f, f.name);
});

$("run-voice").addEventListener("click", () =>
  busy($("run-voice"), "voice-status", "Transcribing…", async () => {
    showError("voice-error", null);
    try {
      const ref = $("voice-ref").value.trim();
      const r = await api.testAudio(voiceBlob, voiceName, ref);
      const block = (cond) => {
        const line = (key, tag, cls) => `<div class="hyp"><span class="tag ${cls}">${tag}</span>
          ${ref ? `<span class="cer">CER ${pct(r[`${key}_cer`])}</span>` : ""}
          <div class="diff">${ref ? diffHtml(ref, r[key]) : escapeHtml(r[key] || "(nothing recognised)")}</div></div>`;
        return `<div class="cond"><div class="name">${cond} · ${r.conditions[cond]}</div>
          <audio controls src="${r.audio[cond]}"></audio>${line(cond, "F0", "f0")}${line(`${cond}_F3`, "F3", "f3")}</div>`;
      };
      $("voice-results").innerHTML = `<div class="card"><div class="grid2">${block("C1")}${block(r.phone_condition)}</div>
        <p class="status">${r.seconds} s of audio · processed in ${(r.elapsed_ms / 1000).toFixed(1)} s · nothing stored</p></div>`;
      $("voice-status").textContent = "";
      checkHealth();
    } catch (e) {
      $("voice-status").textContent = "";
      showError("voice-error", e);
    }
  })
);

// ---------- score / fix ----------
$("run-score").addEventListener("click", () =>
  busy($("run-score"), "score-status", "Scoring…", async () => {
    try {
      const variants = $("score-var").value.split("|").map((s) => s.trim()).filter(Boolean);
      const r = await api.score($("score-ref").value, $("score-hyp").value, variants);
      $("score-results").innerHTML = `
        <div class="tiles">
          <div class="tile"><div class="v">${pct(r.cer)}</div><div class="k">Character error rate (${r.char_edits} edits)</div></div>
          <div class="tile"><div class="v">${pct(r.wer)}</div><div class="k">Word error rate (${r.word_edits} edits)</div></div>
          <div class="tile"><div class="v">${r.numbers.matched}/${r.numbers.in_reference}</div><div class="k">Numbers recovered</div></div>
        </div>
        <div class="card"><div class="diff">${diffHtml(r.reference_used, r.hypothesis_normalised)}</div></div>`;
      $("score-status").textContent = "0 API calls";
    } catch (e) {
      $("score-status").textContent = "";
      $("score-results").innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
    }
  })
);

$("run-fix").addEventListener("click", () =>
  busy($("run-fix"), "fix-status", "Fixing…", async () => {
    try {
      const r = await api.fix($("fix-in").value);
      $("fix-results").innerHTML = `<div class="card"><div class="diff">${diffHtml($("fix-in").value, r.text)}</div>
        <p class="status">${r.rules_applied.length} rule(s) applied · 0 API calls</p>
        <textarea class="ta" readonly style="min-height:60px">${escapeHtml(r.text)}</textarea></div>`;
      $("fix-status").textContent = "";
    } catch (e) {
      $("fix-status").textContent = "";
      $("fix-results").innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
    }
  })
);

// ---------- benchmark ----------
async function loadBench() {
  const box = $("bench-results");
  try {
    const r = await api.latest("test");
    const settings = [...new Set(r.overall.map((x) => x.setting))].sort();
    const conds = ["C1", "C2", "C3", "C4"];
    const tables = ["real", "timbre"].map((src) => {
      const rows = r.overall.filter((x) => x.source === src);
      if (!rows.length) return "";
      const cell = (c, s) => {
        const x = rows.find((y) => y.condition === c && y.setting === s);
        return x ? `${pct(x.cer.value)} <span class="cer">(${pct(x.cer.low)}–${pct(x.cer.high)})</span>` : "–";
      };
      const n = (c) => rows.find((y) => y.condition === c)?.n ?? "–";
      return `<div class="card"><h3>${src === "real" ? "Real recordings" : "Synthetic (Timbre)"}</h3>
        <table><tr><th>Condition</th><th>n</th>${settings.map((s) => `<th>${s}</th>`).join("")}</tr>
        ${conds.map((c) => `<tr><td>${c} ${COND_LABEL[c]}</td><td class="num">${n(c)}</td>${settings.map((s) => `<td class="num">${cell(c, s)}</td>`).join("")}</tr>`).join("")}
        </table></div>`;
    }).join("");
    const lat = r.meta.latency_ms || {};
    box.innerHTML = `<p class="status">Run ${escapeHtml(r.run)} · ${r.meta.n_utterances} utterances · Prisma latency p50 ${lat.p50 ?? "–"} ms, p95 ${lat.p95 ?? "–"} ms</p>
      ${tables}<p class="status">F0 raw · F1 numbers as digits (ITN) · F2 ITN + hint words · F3 F2 + KuralCheck fix layer${settings.includes("W0") ? " · W0 Whisper small" : ""}</p>`;
  } catch (e) {
    box.innerHTML = `<div class="error">${escapeHtml(e.message)}</div>`;
  }
}

// ---------- settings ----------
async function loadSettings() {
  const s = await getSettings();
  $("set-server").value = s.server;
  $("set-token").value = s.token;
}
$("save-settings").addEventListener("click", async () => {
  const server = $("set-server").value.trim() || "http://127.0.0.1:8765";
  if (server.startsWith("https://")) {
    const origin = new URL(server).origin + "/*";
    const ok = await chrome.permissions.request({ origins: [origin] });
    if (!ok) return ($("settings-status").textContent = "Permission for that server was not granted.");
  }
  await saveSettings({ server, token: $("set-token").value.trim() });
  $("settings-status").textContent = "Saved.";
  checkHealth();
});

// ---------- start ----------
(async () => {
  await loadSettings();
  checkHealth();
  const { pendingText } = await chrome.storage.local.get("pendingText");
  if (pendingText) {
    $("text-input").value = pendingText;
    await chrome.storage.local.remove("pendingText");
  }
  const hash = location.hash.replace("#", "");
  if (["text", "voice", "score", "fix", "bench", "settings"].includes(hash)) showTab(hash);
})();
