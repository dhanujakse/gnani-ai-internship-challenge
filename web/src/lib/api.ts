// Talks to the Sarvagyan server the same way the Android app does (data/ApiClient.kt).
// Access tokens last 15 minutes; on a 401 we refresh once with the refresh token, like the app.

export const SERVER_URL = (process.env.NEXT_PUBLIC_SERVER_URL || "https://sarvagyan-server.onrender.com").replace(/\/+$/, "");
export const WS_URL = SERVER_URL.replace(/^http/, "ws");
const DEVICE = "Web browser";
const STORE_KEY = "sarvagyan.session";

export interface User {
  id: string;
  display_name: string;
  username?: string | null;
  email?: string | null;
  avatar?: string | null;
  is_demo?: boolean;
  language: string;
  allow_calls?: "everyone" | "contacts";
}

export interface Session {
  token: string;
  refresh_token: string;
  user: User;
}

export interface Language {
  code: string;
  name: string;
  native: string;
}

export interface Contact {
  id: string;
  name: string;
  username?: string | null;
  language: string;
  avatar?: string | null;
  is_demo?: boolean;
}

export interface CallRecord {
  call_id: string;
  status: string;
  outcome?: string | null;
  has_voicemail?: boolean;
  created_at: number;
  duration_s?: number | null;
  utterances: number;
  my_language: string;
  peer?: { id: string; name?: string | null; language: string; is_demo?: boolean; avatar?: string | null; favourite?: boolean } | null;
}

export interface CallInfo {
  call_id: string;
  invite_code: string;
  invite_link: string;
  participants: number;
  ringing?: boolean;
  reachable?: boolean;
  call_state?: string;
  peer_id?: string;
  peer_name?: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
  get isAuth() {
    return this.status === 401;
  }
}

// Same fallback list as the app (FallbackLanguages), used until /v1/languages answers.
export const FALLBACK_LANGUAGES: Language[] = [
  { code: "ta-IN", name: "Tamil", native: "தமிழ்" },
  { code: "en-IN", name: "English", native: "English" },
  { code: "hi-IN", name: "Hindi", native: "हिन्दी" },
  { code: "te-IN", name: "Telugu", native: "తెలుగు" },
  { code: "kn-IN", name: "Kannada", native: "ಕನ್ನಡ" },
  { code: "ml-IN", name: "Malayalam", native: "മലയാളം" },
  { code: "mr-IN", name: "Marathi", native: "मराठी" },
  { code: "bn-IN", name: "Bengali", native: "বাংলা" },
  { code: "gu-IN", name: "Gujarati", native: "ગુજરાતી" },
  { code: "pa-IN", name: "Punjabi", native: "ਪੰਜਾਬੀ" },
];

// ---------- session storage (this browser only) ----------

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(s: Session | null) {
  try {
    if (s) localStorage.setItem(STORE_KEY, JSON.stringify(s));
    else localStorage.removeItem(STORE_KEY);
  } catch {
    /* private mode: the session simply lasts for this tab */
  }
  sessionListeners.forEach((l) => l(s));
}

const sessionListeners = new Set<(s: Session | null) => void>();
export function onSessionChange(l: (s: Session | null) => void) {
  sessionListeners.add(l);
  return () => {
    sessionListeners.delete(l);
  };
}

// useSyncExternalStore helpers: a stable snapshot that only changes when the stored session does.
let snapCache: { raw: string | null; value: Session | null } = { raw: null, value: null };
export function sessionSnapshot(): Session | null {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(STORE_KEY);
  } catch {
    raw = null;
  }
  if (raw !== snapCache.raw) {
    let value: Session | null = null;
    try {
      value = raw ? (JSON.parse(raw) as Session) : null;
    } catch {
      value = null;
    }
    snapCache = { raw, value };
  }
  return snapCache.value;
}
export function subscribeSession(onChange: () => void) {
  const off = onSessionChange(() => onChange());
  const storage = (e: StorageEvent) => e.key === STORE_KEY && onChange(); // other tabs
  window.addEventListener("storage", storage);
  return () => {
    off();
    window.removeEventListener("storage", storage);
  };
}

// ---------- requests ----------

function messageFrom(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string; loc?: string[] };
    const field = first.loc?.[first.loc.length - 1];
    if (field === "password") return "Password must be at least 8 characters.";
    if (field === "email") return "Enter a valid email address.";
    return first.msg || "Please check the details and try again.";
  }
  if (status === 429) return "Too many attempts. Please wait a minute and try again.";
  if (status >= 500) return "The server had a problem. Please try again.";
  return "Something went wrong. Please try again.";
}

let refreshing: Promise<boolean> | null = null;

async function refresh(): Promise<boolean> {
  const s = loadSession();
  if (!s?.refresh_token) return false;
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${SERVER_URL}/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: s.refresh_token }),
      });
      if (!r.ok) return false;
      const next = (await r.json()) as Session;
      saveSession({ ...s, ...next, user: next.user ?? s.user });
      return true;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

export async function api<T>(path: string, init: { method?: string; body?: unknown; raw?: BodyInit; auth?: boolean } = {}, retried = false): Promise<T> {
  const { method = "GET", body, raw, auth = true } = init;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const s = loadSession();
  if (auth && s) headers["Authorization"] = `Bearer ${s.token}`;
  let r: Response;
  try {
    r = await fetch(`${SERVER_URL}${path}`, { method, headers, body: raw ?? (body !== undefined ? JSON.stringify(body) : undefined) });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your internet and try again.");
  }
  if (r.status === 401 && auth && !retried && s && !path.startsWith("/v1/auth/")) {
    if (await refresh()) return api<T>(path, init, true);
    saveSession(null);
    throw new ApiError(401, "Please sign in again.");
  }
  const text = await r.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* not JSON */
  }
  if (!r.ok) throw new ApiError(r.status, messageFrom(r.status, json));
  return json as T;
}

// ---------- endpoints (names follow the app) ----------

export const Api = {
  login: (email: string, password: string) => api<Session>("/v1/auth/login", { method: "POST", body: { email, password, device: DEVICE }, auth: false }),
  register: (b: { email: string; password: string; name: string; username: string; language: string; phoneHash?: string | null }) =>
    api<Session>("/v1/auth/register", {
      method: "POST",
      auth: false,
      body: { email: b.email, password: b.password, display_name: b.name, username: b.username, language: b.language, device: DEVICE, phone_hash: b.phoneHash ?? null },
    }),
  logout: () => api<unknown>("/v1/auth/logout", { method: "POST" }).catch(() => undefined),
  checkUsername: (u: string) => api<{ available: boolean; reason?: string }>(`/v1/users/check-username?username=${encodeURIComponent(u)}`, { auth: false }),
  languages: () => api<{ languages: Language[] }>("/v1/languages", { auth: false }),
  me: () => api<User>("/v1/me"),
  updateMe: (patch: Partial<{ display_name: string; language: string; allow_calls: string; avatar: string; phone_hash: string }>) =>
    api<User>("/v1/me", { method: "PATCH", body: patch }),
  uploadAvatar: (file: Blob) => api<User>("/v1/me/avatar", { method: "POST", raw: file }),
  contacts: () => api<{ contacts: Contact[] }>("/v1/contacts"),
  addContact: (username: string) => api<{ contact: Contact }>("/v1/contacts", { method: "POST", body: { username } }),
  favourites: () => api<{ contacts: Contact[] }>("/v1/contacts/favourites"),
  setFavourite: (id: string, on: boolean) => api<unknown>(`/v1/contacts/favourites/${id}`, { method: on ? "PUT" : "DELETE" }),
  history: () => api<{ calls: CallRecord[] }>("/v1/calls/history"),
  createCall: (language: string) => api<CallInfo>("/v1/calls", { method: "POST", body: { language } }),
  joinCall: (code: string, language: string) => api<CallInfo>("/v1/calls/join", { method: "POST", body: { code, language } }),
  callPerson: (to: string, language: string) => api<CallInfo>("/v1/calls/direct", { method: "POST", body: { to, language } }),
  answer: (cid: string, language: string) => api<CallInfo>(`/v1/calls/${cid}/answer`, { method: "POST", body: { language } }),
  decline: (cid: string) => api<unknown>(`/v1/calls/${cid}/decline`, { method: "POST" }),
  cancel: (cid: string) => api<unknown>(`/v1/calls/${cid}/cancel`, { method: "POST" }),
  diagnostics: () => api<Record<string, unknown>>("/v1/diagnostics"),
  avatarBlob: async (fid: string, thumb: boolean) => {
    const s = loadSession();
    const r = await fetch(`${SERVER_URL}/v1/avatars/${fid}?thumb=${thumb}`, { headers: s ? { Authorization: `Bearer ${s.token}` } : {} });
    if (!r.ok) throw new ApiError(r.status, "Avatar not found.");
    return r.blob();
  },
};

/** The same 6-character invitation code clean-up as the app (normaliseCode). */
export function normaliseCode(raw: string) {
  return raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
}
