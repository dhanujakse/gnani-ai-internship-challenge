// Shared client for the KuralCheck API server. The Gnani key never lives in the extension.

export const DEFAULTS = { server: "http://127.0.0.1:8765", token: "" };

export async function getSettings() {
  const stored = await chrome.storage.local.get(["server", "token"]);
  return { ...DEFAULTS, ...stored };
}

export async function saveSettings(settings) {
  await chrome.storage.local.set(settings);
}

async function request(path, { method = "GET", json, form, timeoutMs = 120000 } = {}) {
  const { server, token } = await getSettings();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  const started = performance.now();
  let res;
  try {
    res = await fetch(server.replace(/\/$/, "") + path, { method, headers, body, signal: ctrl.signal });
  } catch (err) {
    throw new Error(
      err.name === "AbortError"
        ? "The server took too long to answer."
        : `Cannot reach the KuralCheck server at ${server}. Start it with: uv run uvicorn kuralcheck.api:app --port 8765`
    );
  } finally {
    clearTimeout(timer);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
    throw new Error(`${res.status}: ${detail}`);
  }
  data._roundTripMs = Math.round(performance.now() - started);
  return data;
}

export const api = {
  health: () => request("/health", { timeoutMs: 5000 }),
  latest: (split = "test") => request(`/v1/results/latest?split=${encodeURIComponent(split)}`),
  score: (reference, hypothesis, accepted_variants = []) =>
    request("/v1/score", { method: "POST", json: { reference, hypothesis, accepted_variants } }),
  fix: (text) => request("/v1/fix", { method: "POST", json: { text } }),
  testText: (sentences, voice) => request("/v1/test-text", { method: "POST", json: { sentences, voice } }),
  testAudio: (blob, filename, reference) => {
    const form = new FormData();
    form.append("file", blob, filename);
    form.append("reference", reference || "");
    return request("/v1/test-audio", { method: "POST", form });
  },
};

// --- small UI helpers shared by the popup and the tester page -----------------------

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/** Word-level diff (LCS): missed reference words struck, inserted words underlined. */
export function diffHtml(reference, hypothesis) {
  const a = String(reference || "").replace(/[.,!?।]/g, "").split(/\s+/).filter(Boolean);
  const b = String(hypothesis || "").replace(/[.,!?।]/g, "").split(/\s+/).filter(Boolean);
  const dp = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out = [];
  let i = 0, j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) { out.push(escapeHtml(a[i])); i++; j++; }
    else if (j < b.length && (i >= a.length || dp[i][j + 1] > dp[i + 1][j])) { out.push(`<ins>${escapeHtml(b[j])}</ins>`); j++; }
    else { out.push(`<del>${escapeHtml(a[i])}</del>`); i++; }
  }
  return out.join(" ");
}

export const pct = (x) => (x === null || x === undefined || Number.isNaN(x) ? "–" : `${(100 * x).toFixed(1)}%`);
