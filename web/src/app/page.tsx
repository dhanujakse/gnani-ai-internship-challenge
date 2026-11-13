"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";

const SERVER_URL = "https://sarvagyan-server.onrender.com";
const WS_URL = "wss://sarvagyan-server.onrender.com";

const LANGUAGES = [
  { code: "ta-IN", native: "தமிழ்", name: "Tamil" },
  { code: "en-IN", native: "English", name: "English" },
  { code: "hi-IN", native: "हिन्दी", name: "Hindi" },
  { code: "te-IN", native: "తెలుగు", name: "Telugu" },
  { code: "kn-IN", native: "ಕನ್ನಡ", name: "Kannada" },
  { code: "ml-IN", native: "മലയാളം", name: "Malayalam" },
  { code: "mr-IN", native: "मराठी", name: "Marathi" },
  { code: "bn-IN", native: "বাংলা", name: "Bengali" },
  { code: "gu-IN", native: "ગુજરાતી", name: "Gujarati" },
  { code: "pa-IN", native: "ਪੰਜਾਬੀ", name: "Punjabi" },
];

interface UserProfile {
  id: string;
  display_name: string;
  email?: string;
  username?: string;
  language: string;
  is_demo?: boolean;
}

interface CallHistoryItem {
  call_id: string;
  status: string;
  duration_s?: number;
  created_at: number;
  my_language: string;
  peer?: {
    id: string;
    name: string;
    language: string;
  };
}

interface ContactItem {
  id: string;
  name: string;
  username?: string;
  language: string;
}

interface Utterance {
  id: string;
  speakerId: string;
  original: string;
  translation?: string;
  stage: string;
  mine: boolean;
}

function SarvagyanAppContent() {
  const searchParams = useSearchParams();
  const queryCode = searchParams.get("code") || searchParams.get("join") || "";

  // Auth & Session
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string>("");
  const [authMode, setAuthMode] = useState<"signin" | "register">("signin");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authDisplayName, setAuthDisplayName] = useState("");
  const [authLanguage, setAuthLanguage] = useState("ta-IN");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  // Dashboard Navigation
  const [activeTab, setActiveTab] = useState<"dialer" | "recents" | "contacts" | "diagnostics" | "settings">("dialer");

  // Dialer Tab State
  const [dialCode, setDialCode] = useState(queryCode.toUpperCase());
  const [callLang, setCallLang] = useState("ta-IN");
  const [dialLoading, setDialLoading] = useState(false);
  const [createdRoomInfo, setCreatedRoomInfo] = useState<{ code: string; link: string } | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  // Recents State
  const [history, setHistory] = useState<CallHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Contacts State
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [newContactUsername, setNewContactUsername] = useState("");
  const [addContactError, setAddContactError] = useState("");

  // Diagnostics State
  const [diagResult, setDiagResult] = useState<Record<string, unknown> | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);

  // Active In-Call State
  const [activeCallId, setActiveCallId] = useState<string | null>(null);
  const [activeCallCode, setActiveCallCode] = useState<string>("");
  const [peerName, setPeerName] = useState<string | null>(null);
  const [peerLang, setPeerLang] = useState<string | null>(null);
  const [turns, setTurns] = useState<Utterance[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [peerSpeaking, setPeerSpeaking] = useState(false);
  const [callDuration, setCallDuration] = useState(0);

  // Audio & WebSockets
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const transcriptsEndRef = useRef<HTMLDivElement | null>(null);

  // Load Saved Auth from localStorage
  useEffect(() => {
    try {
      const savedToken = localStorage.getItem("sarvagyan_token");
      const savedUser = localStorage.getItem("sarvagyan_user");
      if (savedToken && savedUser) {
        setToken(savedToken);
        const parsedUser = JSON.parse(savedUser);
        setUser(parsedUser);
        setCallLang(parsedUser.language || "ta-IN");
      }
    } catch {}
  }, []);

  // Timer for active call
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (activeCallId) {
      interval = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      setCallDuration(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [activeCallId]);

  // Auto-scroll transcripts
  useEffect(() => {
    transcriptsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  // Load Tab Data when tab changes
  useEffect(() => {
    if (!token) return;
    if (activeTab === "recents") {
      loadHistory();
    } else if (activeTab === "contacts") {
      loadContacts();
    } else if (activeTab === "diagnostics") {
      runDiagnostics();
    }
  }, [activeTab, token]);

  // Auto-join if URL has ?code=
  useEffect(() => {
    if (queryCode && token) {
      setDialCode(queryCode.toUpperCase());
    }
  }, [queryCode, token]);

  // ---------------- AUTH HANDLERS ----------------
  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    setAuthError("");

    try {
      if (authMode === "signin") {
        const res = await fetch(`${SERVER_URL}/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: authEmail.trim(),
            password: authPassword,
            device: "Web Browser",
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Invalid email or password.");
        }
        const data = await res.json();
        setToken(data.token);
        setUser(data.user);
        setCallLang(data.user.language || "ta-IN");
        localStorage.setItem("sarvagyan_token", data.token);
        localStorage.setItem("sarvagyan_user", JSON.stringify(data.user));
      } else {
        const res = await fetch(`${SERVER_URL}/v1/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: authEmail.trim(),
            password: authPassword,
            display_name: authDisplayName.trim() || "User",
            language: authLanguage,
            device: "Web Browser",
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Registration failed.");
        }
        const data = await res.json();
        setToken(data.token);
        setUser(data.user);
        setCallLang(data.user.language || "ta-IN");
        localStorage.setItem("sarvagyan_token", data.token);
        localStorage.setItem("sarvagyan_user", JSON.stringify(data.user));
      }
    } catch (err: unknown) {
      setAuthError(err instanceof Error ? err.message : "Authentication error.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem("sarvagyan_token");
    localStorage.removeItem("sarvagyan_user");
    setUser(null);
    setToken("");
    endCall();
  };

  // ---------------- CALL & WEBSOCKET ENGINE ----------------
  const startMicrophone = async (ws: WebSocket) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)({
        sampleRate: 16000,
      });
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(512, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);

        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        ws.send(pcm16.buffer);
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);
    } catch (err) {
      console.error("Microphone error:", err);
    }
  };

  const playAudioChunk = async (blob: Blob) => {
    try {
      const buffer = await blob.arrayBuffer();
      const pcm16 = new Int16Array(buffer);
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / 32768.0;
      }

      const audioCtx = audioContextRef.current || new AudioContext({ sampleRate: 16000 });
      const audioBuffer = audioCtx.createBuffer(1, float32.length, 16000);
      audioBuffer.copyToChannel(float32, 0);

      const srcNode = audioCtx.createBufferSource();
      srcNode.buffer = audioBuffer;
      srcNode.connect(audioCtx.destination);
      srcNode.start();
    } catch (e) {
      console.error("Audio playback error:", e);
    }
  };

  const connectToCallWs = async (cid: string, codeStr: string, myLang: string) => {
    setActiveCallId(cid);
    setActiveCallCode(codeStr);
    setTurns([]);

    const ws = new WebSocket(`${WS_URL}/v1/calls/${cid}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "hello", language: myLang }));
    };

    ws.onmessage = async (event) => {
      if (typeof event.data === "string") {
        try {
          const msg = JSON.parse(event.data);
          handleServerMessage(msg);
        } catch {}
      } else if (event.data instanceof Blob) {
        playAudioChunk(event.data);
      }
    };

    ws.onclose = () => {
      endCall();
    };

    await startMicrophone(ws);
  };

  const handleServerMessage = (msg: Record<string, unknown>) => {
    switch (msg.type) {
      case "joined":
      case "peer_joined": {
        const peer = (msg.peer as Record<string, unknown>) || {};
        if (peer.name) setPeerName(String(peer.name));
        if (peer.language) setPeerLang(String(peer.language));
        break;
      }
      case "speech_activity": {
        if (msg.speaker_id === user?.id) {
          setIsSpeaking(Boolean(msg.active));
        } else {
          setPeerSpeaking(Boolean(msg.active));
        }
        break;
      }
      case "utterance": {
        const uId = String(msg.id);
        const speakerId = String(msg.speaker_id);
        const orig = String(msg.original || "");
        const trans = (msg.translation as string) || undefined;
        const stage = String(msg.stage || "");

        setTurns((prev) => {
          const idx = prev.findIndex((t) => t.id === uId);
          const updated: Utterance = {
            id: uId,
            speakerId,
            original: orig,
            translation: trans,
            stage,
            mine: speakerId === user?.id,
          };
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = updated;
            return next;
          }
          return [...prev, updated];
        });
        break;
      }
      case "peer_left": {
        endCall();
        break;
      }
    }
  };

  const handleCreateRoom = async () => {
    setDialLoading(true);
    try {
      const res = await fetch(`${SERVER_URL}/v1/calls`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ language: callLang }),
      });
      if (!res.ok) throw new Error("Could not create call.");
      const data = await res.json();
      const currentOrigin = typeof window !== "undefined" ? window.location.origin : "";
      const inviteLink = `${currentOrigin}/join?code=${data.invite_code}`;
      setCreatedRoomInfo({ code: data.invite_code, link: inviteLink });
      await connectToCallWs(data.call_id, data.invite_code, callLang);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Error creating room");
    } finally {
      setDialLoading(false);
    }
  };

  const handleJoinCallByCode = async () => {
    const clean = dialCode.trim().toUpperCase();
    if (!clean) return;
    setDialLoading(true);
    try {
      const res = await fetch(`${SERVER_URL}/v1/calls/join`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ code: clean, language: callLang }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Call not found. Check the code.");
      }
      const data = await res.json();
      await connectToCallWs(data.call_id, clean, callLang);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Error joining call");
    } finally {
      setDialLoading(false);
    }
  };

  const toggleMute = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getAudioTracks().forEach((track) => {
        track.enabled = isMuted;
      });
      setIsMuted(!isMuted);
    }
  };

  const endCall = () => {
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: "leave" }));
      } catch {}
      wsRef.current.close();
      wsRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setActiveCallId(null);
    setActiveCallCode("");
    setPeerName(null);
    setPeerLang(null);
    setIsSpeaking(false);
    setPeerSpeaking(false);
  };

  // ---------------- RECENTS, CONTACTS, DIAGNOSTICS ----------------
  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await fetch(`${SERVER_URL}/v1/calls/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.calls || []);
      }
    } catch {}
    setHistoryLoading(false);
  };

  const loadContacts = async () => {
    setContactsLoading(true);
    try {
      const res = await fetch(`${SERVER_URL}/v1/contacts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setContacts(data.contacts || []);
      }
    } catch {}
    setContactsLoading(false);
  };

  const handleAddContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContactUsername.trim()) return;
    setAddContactError("");
    try {
      const res = await fetch(`${SERVER_URL}/v1/contacts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ username: newContactUsername.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Contact not found.");
      }
      setNewContactUsername("");
      loadContacts();
    } catch (err: unknown) {
      setAddContactError(err instanceof Error ? err.message : "Failed to add contact.");
    }
  };

  const runDiagnostics = async () => {
    setDiagLoading(true);
    try {
      const res = await fetch(`${SERVER_URL}/v1/diagnostics`);
      if (res.ok) {
        const data = await res.json();
        setDiagResult(data);
      }
    } catch {}
    setDiagLoading(false);
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // ==================== 1. AUTH SCREEN (IF NOT LOGGED IN) ====================
  if (!user || !token) {
    return (
      <div className="min-h-screen bg-[#071B20] text-[#F5F7F2] flex flex-col justify-between selection:bg-[#00CBA0] selection:text-[#071B20]">
        {/* Top Header */}
        <header className="w-full max-w-7xl mx-auto px-6 py-6 flex items-center justify-between border-b border-[#1E4D53]/30">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl overflow-hidden shadow-lg shadow-[#00CBA0]/20 border border-[#00CBA0]/40 shrink-0" style={{ width: 44, height: 44 }}>
              <Image src="/logo.png" alt="Sarvagyan" width={44} height={44} className="w-full h-full object-cover" priority style={{ width: 44, height: 44, objectFit: "cover" }} />
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-[#F5F7F2] block leading-none">
                Sarvagyan (सर्वज्ञान)
              </span>
              <span className="text-[10px] tracking-wider uppercase text-[#00CBA0] font-mono">
                Real-Time Multilingual Voice Calling
              </span>
            </div>
          </div>
          <a
            href="/Sarvagyan.apk"
            download
            className="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-[#00CBA0] transition-colors"
          >
            Download Android APK (58 MB)
          </a>
        </header>

        {/* Widescreen Hero Auth Stage */}
        <main className="flex-1 w-full max-w-6xl mx-auto px-6 py-12 flex items-center justify-center">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center w-full">
            {/* Left Column: Brand Showcase */}
            <div className="lg:col-span-6 flex flex-col items-start text-left">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#12363A]/80 border border-[#1E4D53] text-xs font-semibold tracking-wide text-[#00CBA0] mb-6">
                <span className="w-2 h-2 rounded-full bg-[#00F0A0] animate-ping" />
                Gnani AI Prisma & Timbre
              </div>

              <h1 className="text-4xl sm:text-5xl font-black tracking-tight text-[#F5F7F2] leading-tight">
                Speak in your tongue. <br />
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#00CBA0] via-[#00F0A0] to-[#F5B52E]">
                  They understand instantly.
                </span>
              </h1>

              <p className="mt-5 text-base text-[#A9BFBA] max-w-lg leading-relaxed">
                Full-featured multilingual phone and web calls across 10 Indian languages. Connect from your browser with live neural voice synthesis, real-time speech translation, and bilingual subtitles.
              </p>

              <div className="mt-8 grid grid-cols-2 gap-3 w-full max-w-md">
                <div className="p-3.5 rounded-2xl bg-[#0B292E]/60 border border-[#1E4D53]/60">
                  <span className="text-xs font-bold text-[#00CBA0] block">Tamil ⇄ Hindi</span>
                  <span className="text-[11px] text-[#A9BFBA]">Live voice conversion</span>
                </div>
                <div className="p-3.5 rounded-2xl bg-[#0B292E]/60 border border-[#1E4D53]/60">
                  <span className="text-xs font-bold text-[#F5B52E] block">10 Indian Languages</span>
                  <span className="text-[11px] text-[#A9BFBA]">Full duplex STT & TTS</span>
                </div>
              </div>
            </div>

            {/* Right Column: Auth Card */}
            <div className="lg:col-span-6 flex justify-center">
              <div className="w-full max-w-md p-8 rounded-3xl glow-card border border-[#1E4D53]/70 bg-[#0B292E]/80 backdrop-blur-md">
                <div className="flex items-center justify-between mb-6 pb-3 border-b border-[#1E4D53]/40">
                  <button
                    onClick={() => { setAuthMode("signin"); setAuthError(""); }}
                    className={`text-sm font-bold pb-1 transition-all ${
                      authMode === "signin"
                        ? "text-[#00CBA0] border-b-2 border-[#00CBA0]"
                        : "text-[#A9BFBA] hover:text-[#F5F7F2]"
                    }`}
                  >
                    Sign In
                  </button>
                  <button
                    onClick={() => { setAuthMode("register"); setAuthError(""); }}
                    className={`text-sm font-bold pb-1 transition-all ${
                      authMode === "register"
                        ? "text-[#00CBA0] border-b-2 border-[#00CBA0]"
                        : "text-[#A9BFBA] hover:text-[#F5F7F2]"
                    }`}
                  >
                    Create Account
                  </button>
                </div>

                {authError && (
                  <div className="mb-4 p-3 rounded-xl bg-[#C62845]/20 border border-[#C62845]/50 text-xs text-[#F5F7F2] text-center">
                    {authError}
                  </div>
                )}

                <form onSubmit={handleAuth} className="space-y-4">
                  {authMode === "register" && (
                    <>
                      <div>
                        <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-1.5">
                          Your Full Name
                        </label>
                        <input
                          type="text"
                          required
                          value={authDisplayName}
                          onChange={(e) => setAuthDisplayName(e.target.value)}
                          placeholder="e.g. Dhanuja Kumar"
                          className="w-full px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-1.5">
                          Your Primary Language
                        </label>
                        <select
                          value={authLanguage}
                          onChange={(e) => setAuthLanguage(e.target.value)}
                          className="w-full px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                        >
                          {LANGUAGES.map((l) => (
                            <option key={l.code} value={l.code} className="bg-[#071B20]">
                              {l.native} — {l.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </>
                  )}

                  <div>
                    <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-1.5">
                      Email Address
                    </label>
                    <input
                      type="email"
                      required
                      value={authEmail}
                      onChange={(e) => setAuthEmail(e.target.value)}
                      placeholder="name@example.com"
                      className="w-full px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-1.5">
                      Password
                    </label>
                    <input
                      type="password"
                      required
                      minLength={8}
                      value={authPassword}
                      onChange={(e) => setAuthPassword(e.target.value)}
                      placeholder="At least 8 characters"
                      className="w-full px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={authLoading}
                    className="w-full mt-4 py-3.5 px-6 rounded-xl font-bold glow-button disabled:opacity-50 text-sm tracking-wide shadow-lg"
                  >
                    {authLoading
                      ? "Connecting..."
                      : authMode === "signin"
                      ? "Sign In to Sarvagyan"
                      : "Create My Account"}
                  </button>
                </form>

                <div className="mt-6 pt-4 border-t border-[#1E4D53]/40 text-center">
                  <Link
                    href={`/join${queryCode ? `?code=${queryCode}` : ""}`}
                    className="text-xs text-[#00CBA0] hover:underline font-semibold"
                  >
                    Quick Join an Active Call via Code without Signing In →
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="w-full max-w-7xl mx-auto px-6 py-4 flex items-center justify-between border-t border-[#1E4D53]/30 text-xs text-[#A9BFBA]">
          <p>© 2026 Sarvagyan · Primary Native Android App & Secondary Web Client</p>
          <a href="/Sarvagyan.apk" download className="hover:text-[#00CBA0]">
            Download APK
          </a>
        </footer>
      </div>
    );
  }

  // ==================== 2. IN-CALL FULLSCREEN STUDIO ====================
  if (activeCallId) {
    const myLangObj = LANGUAGES.find((l) => l.code === callLang);
    const peerLangObj = LANGUAGES.find((l) => l.code === peerLang);

    return (
      <div className="min-h-screen bg-[#071B20] text-[#F5F7F2] flex flex-col justify-between selection:bg-[#00CBA0] selection:text-[#071B20]">
        {/* Call Top Deck */}
        <header className="w-full px-8 py-4 flex items-center justify-between border-b border-[#1E4D53]/40 bg-[#0B292E]/60 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-[#00F0A0] animate-pulse" />
            <span className="font-bold text-sm tracking-tight text-[#F5F7F2]">
              Sarvagyan Live Call · Room #{activeCallCode}
            </span>
          </div>

          <div className="flex items-center gap-4">
            <span className="font-mono text-xs px-3 py-1 rounded-full bg-[#071B20] border border-[#1E4D53] text-[#00CBA0]">
              ⏱ {formatSeconds(callDuration)}
            </span>
            <button
              onClick={() => {
                const url = `${window.location.origin}/join?code=${activeCallCode}`;
                navigator.clipboard.writeText(url);
                alert(`Invite link copied:\n${url}`);
              }}
              className="px-3.5 py-1.5 rounded-xl bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-xs font-semibold text-[#00CBA0] transition-colors"
            >
              Copy Call Link
            </button>
            <button
              onClick={endCall}
              className="px-4 py-1.5 rounded-xl bg-[#C62845] hover:bg-[#C62845]/80 text-xs font-bold text-white transition-colors"
            >
              End Call
            </button>
          </div>
        </header>

        {/* Widescreen 16:9 / 16:10 Active Call Canvas */}
        <main className="flex-1 w-full max-w-7xl mx-auto px-6 lg:px-12 py-6 flex items-stretch">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full items-stretch">
            {/* Left Column (5 cols): Participant Presence Tiles & Voice Visualizers */}
            <div className="lg:col-span-5 flex flex-col gap-4 justify-between">
              {/* Partner Card */}
              <div className="flex-1 rounded-3xl p-6 bg-gradient-to-br from-[#0B292E] to-[#071B20] border border-[#1E4D53] shadow-xl flex flex-col justify-between min-h-[220px]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${peerSpeaking ? "bg-[#00F0A0] animate-ping" : "bg-[#A9BFBA]"}`} />
                    <span className="text-xs font-mono uppercase tracking-wider text-[#A9BFBA]">
                      Partner
                    </span>
                  </div>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#12363A] text-[#00CBA0] border border-[#1E4D53] font-semibold">
                    {peerLangObj ? `${peerLangObj.native} (${peerLangObj.name})` : "Listening"}
                  </span>
                </div>

                <div className="text-center my-auto py-3">
                  <div className="w-16 h-16 mx-auto rounded-full bg-[#12363A] border-2 border-[#00CBA0]/40 flex items-center justify-center text-2xl font-bold text-[#00CBA0]">
                    {peerName ? peerName[0].toUpperCase() : "P"}
                  </div>
                  <h3 className="text-base font-bold text-[#F5F7F2] mt-3">
                    {peerName || "Waiting for partner to join..."}
                  </h3>
                  <p className="text-xs text-[#A9BFBA] mt-0.5">
                    {peerSpeaking ? "Speaking now..." : "Listening"}
                  </p>
                </div>

                <div className="h-6 flex items-center justify-center gap-1.5">
                  {peerSpeaking ? (
                    <>
                      <span className="w-1 h-3 bg-[#00F0A0] rounded-full animate-bounce [animation-delay:0ms]" />
                      <span className="w-1 h-6 bg-[#00F0A0] rounded-full animate-bounce [animation-delay:150ms]" />
                      <span className="w-1 h-4 bg-[#00F0A0] rounded-full animate-bounce [animation-delay:300ms]" />
                      <span className="w-1 h-6 bg-[#00F0A0] rounded-full animate-bounce [animation-delay:100ms]" />
                      <span className="w-1 h-2 bg-[#00F0A0] rounded-full animate-bounce [animation-delay:250ms]" />
                    </>
                  ) : (
                    <span className="text-[11px] text-[#A9BFBA]/60 font-mono">Audio standby</span>
                  )}
                </div>
              </div>

              {/* Your Card */}
              <div className="rounded-3xl p-6 bg-[#0B292E]/70 border border-[#00CBA0]/30 shadow-xl flex flex-col justify-between min-h-[170px]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${isSpeaking ? "bg-[#00CBA0] animate-ping" : "bg-[#00CBA0]"}`} />
                    <span className="text-xs font-mono uppercase tracking-wider text-[#00CBA0]">
                      You ({user.display_name})
                    </span>
                  </div>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#071B20] text-[#00CBA0] border border-[#1E4D53] font-semibold">
                    {myLangObj?.native} ({myLangObj?.name})
                  </span>
                </div>

                <div className="flex items-center justify-between my-auto py-2">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[#00CBA0]/20 border border-[#00CBA0]/60 flex items-center justify-center font-bold text-[#00CBA0]">
                      {user.display_name[0].toUpperCase()}
                    </div>
                    <div>
                      <span className="text-sm font-bold text-[#F5F7F2] block">{user.display_name}</span>
                      <span className="text-xs text-[#A9BFBA]">
                        {isMuted ? "Muted" : isSpeaking ? "Speaking into mic..." : "Mic ready"}
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={toggleMute}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold transition-colors border ${
                      isMuted
                        ? "bg-[#C62845]/20 border-[#C62845] text-[#F5F7F2]"
                        : "bg-[#12363A] border-[#1E4D53] text-[#00CBA0] hover:bg-[#194449]"
                    }`}
                  >
                    {isMuted ? "Unmute Mic" : "Mute Mic"}
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column (7 cols): Subtitle & Neural Translation Studio */}
            <div className="lg:col-span-7 flex flex-col rounded-3xl glow-card border border-[#1E4D53]/70 bg-[#0B292E]/60 backdrop-blur-md overflow-hidden min-h-[460px]">
              <div className="px-6 py-4 border-b border-[#1E4D53]/40 flex items-center justify-between bg-[#071B20]/60">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#00CBA0]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-[#F5F7F2]">
                    Synchronized Live Subtitles & Neural Audio
                  </span>
                </div>
                <span className="text-[11px] font-mono text-[#A9BFBA]">Gnani Vachana AI</span>
              </div>

              <div className="flex-1 p-6 overflow-y-auto space-y-4 max-h-[500px]">
                {turns.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center text-[#A9BFBA] py-16 space-y-2">
                    <div className="w-12 h-12 rounded-2xl bg-[#12363A] border border-[#1E4D53] flex items-center justify-center text-[#00CBA0]">
                      🎙️
                    </div>
                    <p className="text-sm font-semibold text-[#F5F7F2]">Waiting for conversation...</p>
                    <p className="text-xs max-w-sm">
                      Speak freely in {myLangObj?.name}. The server will transcribe, translate, and speak neural audio in the partner&apos;s language.
                    </p>
                  </div>
                ) : (
                  turns.map((turn) => (
                    <div
                      key={turn.id}
                      className={`p-4 rounded-2xl max-w-[85%] text-sm shadow-sm transition-all ${
                        turn.mine
                          ? "ml-auto bg-[#194449]/90 border border-[#00CBA0]/30 text-right"
                          : "mr-auto bg-[#071B20]/90 border border-[#1E4D53] text-left"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3 mb-1 text-xs font-semibold">
                        <span className={turn.mine ? "text-[#00CBA0]" : "text-[#F5B52E]"}>
                          {turn.mine ? "You" : peerName || "Partner"}
                        </span>
                        <span className="text-[10px] text-[#A9BFBA] font-mono">
                          {turn.stage || "live"}
                        </span>
                      </div>
                      <p className="text-base font-medium text-[#F5F7F2] leading-snug">
                        {turn.original}
                      </p>
                      {turn.translation && (
                        <div className="mt-2 pt-2 border-t border-white/10 text-xs text-[#00F0A0]">
                          <span className="text-[10px] uppercase font-mono text-[#A9BFBA] mr-1 block">
                            {turn.mine ? "Translated to partner:" : "Translated to you:"}
                          </span>
                          {turn.translation}
                        </div>
                      )}
                    </div>
                  ))
                )}
                <div ref={transcriptsEndRef} />
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ==================== 3. MAIN DESKTOP WEB APPLICATION DASHBOARD ====================
  const userLangObj = LANGUAGES.find((l) => l.code === user.language);

  return (
    <div className="min-h-screen bg-[#071B20] text-[#F5F7F2] flex selection:bg-[#00CBA0] selection:text-[#071B20]">
      {/* LEFT SIDEBAR (Desktop 280px, WhatsApp/Discord Web Style) */}
      <aside className="w-72 bg-[#0B292E] border-r border-[#1E4D53]/40 flex flex-col justify-between shrink-0">
        <div>
          {/* Brand Header */}
          <div className="p-5 flex items-center gap-3 border-b border-[#1E4D53]/30">
            <div className="w-10 h-10 rounded-2xl overflow-hidden border border-[#00CBA0]/40 shadow-lg shadow-[#00CBA0]/15 shrink-0" style={{ width: 40, height: 40 }}>
              <Image src="/logo.png" alt="Sarvagyan" width={40} height={40} className="w-full h-full object-cover" priority style={{ width: 40, height: 40, objectFit: "cover" }} />
            </div>
            <div>
              <span className="text-base font-bold tracking-tight text-[#F5F7F2] block leading-none">
                Sarvagyan
              </span>
              <span className="text-[10px] uppercase tracking-wider text-[#00CBA0] font-mono">
                Web Dashboard
              </span>
            </div>
          </div>

          {/* User Profile Pill */}
          <div className="p-4 mx-4 my-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/60 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#12363A] border border-[#00CBA0]/40 flex items-center justify-center font-bold text-sm text-[#00CBA0]">
              {user.display_name[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-sm font-bold text-[#F5F7F2] block truncate">
                {user.display_name}
              </span>
              <span className="text-[11px] text-[#A9BFBA] truncate block">
                {userLangObj ? `${userLangObj.native} (${userLangObj.name})` : user.language}
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="px-3 space-y-1">
            <button
              onClick={() => setActiveTab("dialer")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "dialer"
                  ? "bg-[#194449] text-[#00CBA0] shadow-sm"
                  : "text-[#A9BFBA] hover:text-[#F5F7F2] hover:bg-[#12363A]/50"
              }`}
            >
              <span className="text-base">📞</span>
              <span>Dialer & Instant Call</span>
            </button>

            <button
              onClick={() => setActiveTab("recents")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "recents"
                  ? "bg-[#194449] text-[#00CBA0] shadow-sm"
                  : "text-[#A9BFBA] hover:text-[#F5F7F2] hover:bg-[#12363A]/50"
              }`}
            >
              <span className="text-base">🕒</span>
              <span>Recent Calls</span>
            </button>

            <button
              onClick={() => setActiveTab("contacts")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "contacts"
                  ? "bg-[#194449] text-[#00CBA0] shadow-sm"
                  : "text-[#A9BFBA] hover:text-[#F5F7F2] hover:bg-[#12363A]/50"
              }`}
            >
              <span className="text-base">👥</span>
              <span>Contacts</span>
            </button>

            <button
              onClick={() => setActiveTab("diagnostics")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "diagnostics"
                  ? "bg-[#194449] text-[#00CBA0] shadow-sm"
                  : "text-[#A9BFBA] hover:text-[#F5F7F2] hover:bg-[#12363A]/50"
              }`}
            >
              <span className="text-base">🩺</span>
              <span>System Diagnostics</span>
            </button>

            <button
              onClick={() => setActiveTab("settings")}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "settings"
                  ? "bg-[#194449] text-[#00CBA0] shadow-sm"
                  : "text-[#A9BFBA] hover:text-[#F5F7F2] hover:bg-[#12363A]/50"
              }`}
            >
              <span className="text-base">⚙️</span>
              <span>Settings & Profile</span>
            </button>
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-[#1E4D53]/30 space-y-2">
          <a
            href="/Sarvagyan.apk"
            download
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs font-semibold bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-[#00CBA0] transition-colors"
          >
            <span>Download Android APK</span>
          </a>
          <button
            onClick={handleSignOut}
            className="w-full py-2 px-3 rounded-xl text-xs font-semibold text-[#A9BFBA] hover:text-[#C62845] transition-colors text-center"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT WORKSPACE (Desktop Widescreen Viewport) */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Navbar */}
        <header className="px-8 py-5 border-b border-[#1E4D53]/30 flex items-center justify-between bg-[#071B20]/60 backdrop-blur-md">
          <h2 className="text-xl font-bold text-[#F5F7F2] capitalize">
            {activeTab === "dialer" && "Dialer & Instant Call"}
            {activeTab === "recents" && "Call History"}
            {activeTab === "contacts" && "My Contacts"}
            {activeTab === "diagnostics" && "AI Pipeline Diagnostics"}
            {activeTab === "settings" && "Account & Language Settings"}
          </h2>
          <div className="flex items-center gap-3">
            <span className="text-xs px-3 py-1 rounded-full bg-[#12363A] text-[#00CBA0] border border-[#1E4D53] font-mono">
              Render Cloud Connected
            </span>
          </div>
        </header>

        {/* Tab Content Panes */}
        <div className="p-8 max-w-6xl w-full mx-auto">
          {/* TAB 1: DIALER */}
          {activeTab === "dialer" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Left Column (7 cols): Start Instant Room or Call by Code */}
              <div className="lg:col-span-7 space-y-6">
                {/* Instant Room Creation Card */}
                <div className="glow-card p-6 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/60">
                  <h3 className="text-base font-bold text-[#F5F7F2] mb-1">
                    Start a New Translated Voice Call
                  </h3>
                  <p className="text-xs text-[#A9BFBA] mb-4">
                    Create an instant room and invite anyone on Android or Web with a single link.
                  </p>

                  <div className="mb-4">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#A9BFBA] mb-1.5">
                      Speaking Language for this Call
                    </label>
                    <select
                      value={callLang}
                      onChange={(e) => setCallLang(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                    >
                      {LANGUAGES.map((l) => (
                        <option key={l.code} value={l.code} className="bg-[#071B20]">
                          {l.native} — {l.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    onClick={handleCreateRoom}
                    disabled={dialLoading}
                    className="w-full py-3.5 px-6 rounded-xl font-bold glow-button disabled:opacity-50 text-sm tracking-wide shadow-lg"
                  >
                    {dialLoading ? "Creating Room..." : "Create Room & Start Speaking →"}
                  </button>

                  {createdRoomInfo && (
                    <div className="mt-4 p-4 rounded-2xl bg-[#071B20] border border-[#00CBA0]/40 flex items-center justify-between">
                      <div>
                        <span className="text-[10px] text-[#A9BFBA] uppercase font-mono block">Call Code</span>
                        <span className="text-lg font-mono font-bold text-[#00F0A0]">{createdRoomInfo.code}</span>
                      </div>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(createdRoomInfo.link);
                          setCopiedLink(true);
                          setTimeout(() => setCopiedLink(false), 2000);
                        }}
                        className="px-4 py-2 rounded-xl bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-xs font-bold text-[#00CBA0]"
                      >
                        {copiedLink ? "✓ Copied!" : "Copy Invite Link"}
                      </button>
                    </div>
                  )}
                </div>

                {/* Join Existing Call by Code Card */}
                <div className="glow-card p-6 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/60">
                  <h3 className="text-base font-bold text-[#F5F7F2] mb-1">
                    Join Active Call with Invite Code
                  </h3>
                  <p className="text-xs text-[#A9BFBA] mb-4">
                    Enter the 6-letter room code shared by the other person.
                  </p>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      maxLength={6}
                      value={dialCode}
                      onChange={(e) => setDialCode(e.target.value.toUpperCase())}
                      placeholder="e.g. ABCXYZ"
                      className="flex-1 px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-center font-mono font-bold text-lg uppercase tracking-widest focus:outline-none focus:border-[#00CBA0]"
                    />
                    <button
                      onClick={handleJoinCallByCode}
                      disabled={!dialCode.trim() || dialLoading}
                      className="px-6 py-3 rounded-xl font-bold glow-button disabled:opacity-50 text-sm whitespace-nowrap shadow-md"
                    >
                      Join Call
                    </button>
                  </div>
                </div>
              </div>

              {/* Right Column (5 cols): 10 Indian Languages Quick Reference */}
              <div className="lg:col-span-5 glow-card p-6 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/60">
                <h3 className="text-sm font-bold text-[#F5F7F2] mb-2 uppercase tracking-wider">
                  Supported Languages
                </h3>
                <p className="text-xs text-[#A9BFBA] mb-4">
                  Full duplex bidirectional translation across all pairs:
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {LANGUAGES.map((l) => (
                    <div
                      key={l.code}
                      onClick={() => setCallLang(l.code)}
                      className={`p-2.5 rounded-xl border text-xs cursor-pointer transition-all flex items-center justify-between ${
                        callLang === l.code
                          ? "bg-[#194449] border-[#00CBA0] text-[#00CBA0] font-bold"
                          : "bg-[#071B20]/60 border-[#1E4D53]/60 text-[#F5F7F2] hover:bg-[#12363A]"
                      }`}
                    >
                      <span>{l.native}</span>
                      <span className="text-[10px] text-[#A9BFBA] font-mono">{l.code.split("-")[0]}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: RECENTS */}
          {activeTab === "recents" && (
            <div className="glow-card p-6 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/60">
              <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#1E4D53]/40">
                <span className="text-sm font-bold text-[#F5F7F2]">All Call Logs</span>
                <button
                  onClick={loadHistory}
                  className="text-xs text-[#00CBA0] hover:underline font-semibold"
                >
                  ↻ Refresh History
                </button>
              </div>

              {historyLoading ? (
                <div className="text-center py-12 text-sm text-[#A9BFBA]">Loading past calls...</div>
              ) : history.length === 0 ? (
                <div className="text-center py-16 text-sm text-[#A9BFBA] space-y-2">
                  <div className="text-3xl">📞</div>
                  <p className="font-semibold text-[#F5F7F2]">No recent calls found</p>
                  <p className="text-xs">Start a call from the dialer or join with an invite code.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {history.map((h) => (
                    <div
                      key={h.call_id}
                      className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/60 flex items-center justify-between hover:border-[#00CBA0]/40 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-[#12363A] border border-[#1E4D53] flex items-center justify-center font-bold text-sm text-[#00CBA0]">
                          {h.peer?.name ? h.peer.name[0].toUpperCase() : "C"}
                        </div>
                        <div>
                          <span className="text-sm font-bold text-[#F5F7F2] block">
                            {h.peer?.name || "Group / Web Call"}
                          </span>
                          <span className="text-xs text-[#A9BFBA]">
                            {new Date(h.created_at * 1000).toLocaleDateString()} · {h.duration_s ? `${h.duration_s}s` : "Connected"}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        <span className="text-xs px-2.5 py-1 rounded-full bg-[#12363A] text-[#00CBA0] border border-[#1E4D53] font-mono">
                          {h.my_language}
                        </span>
                        <button
                          onClick={() => {
                            setActiveTab("dialer");
                          }}
                          className="px-4 py-2 rounded-xl bg-[#194449] hover:bg-[#12363A] border border-[#00CBA0]/40 text-xs font-bold text-[#00CBA0]"
                        >
                          Call Again
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: CONTACTS */}
          {activeTab === "contacts" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Contacts List (8 cols) */}
              <div className="lg:col-span-8 glow-card p-6 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/60">
                <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#1E4D53]/40">
                  <span className="text-sm font-bold text-[#F5F7F2]">Saved Contacts</span>
                  <button onClick={loadContacts} className="text-xs text-[#00CBA0] hover:underline font-semibold">
                    ↻ Refresh
                  </button>
                </div>

                {contactsLoading ? (
                  <div className="text-center py-12 text-sm text-[#A9BFBA]">Loading contacts...</div>
                ) : contacts.length === 0 ? (
                  <div className="text-center py-16 text-sm text-[#A9BFBA] space-y-2">
                    <div className="text-3xl">👥</div>
                    <p className="font-semibold text-[#F5F7F2]">No contacts added yet</p>
                    <p className="text-xs">Add a friend by their username or invite them to Sarvagyan.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {contacts.map((c) => (
                      <div
                        key={c.id}
                        className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/60 flex items-center justify-between hover:border-[#00CBA0]/40 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-[#12363A] border border-[#1E4D53] flex items-center justify-center font-bold text-sm text-[#00CBA0]">
                            {c.name[0].toUpperCase()}
                          </div>
                          <div>
                            <span className="text-sm font-bold text-[#F5F7F2] block">{c.name}</span>
                            <span className="text-xs text-[#A9BFBA]">
                              @{c.username || c.id.slice(0, 8)} · {c.language}
                            </span>
                          </div>
                        </div>

                        <button
                          onClick={handleCreateRoom}
                          className="px-4 py-2 rounded-xl bg-[#009B77] hover:bg-[#00CBA0] text-xs font-bold text-[#071B20] transition-colors"
                        >
                          Start Call
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Add Contact Sidebar (4 cols) */}
              <div className="lg:col-span-4 glow-card p-6 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/60 space-y-4">
                <h3 className="text-sm font-bold text-[#F5F7F2] uppercase tracking-wider">
                  Add Contact by Username
                </h3>
                <form onSubmit={handleAddContact} className="space-y-3">
                  <input
                    type="text"
                    required
                    value={newContactUsername}
                    onChange={(e) => setNewContactUsername(e.target.value)}
                    placeholder="Enter @username"
                    className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                  />
                  {addContactError && (
                    <p className="text-xs text-[#C62845]">{addContactError}</p>
                  )}
                  <button
                    type="submit"
                    className="w-full py-2.5 px-4 rounded-xl font-bold glow-button text-xs tracking-wide"
                  >
                    Add Contact
                  </button>
                </form>

                <div className="pt-4 border-t border-[#1E4D53]/40">
                  <h4 className="text-xs font-bold text-[#A9BFBA] mb-2 uppercase">Share Sarvagyan</h4>
                  <button
                    onClick={() => {
                      const url = typeof window !== "undefined" ? window.location.origin : "";
                      navigator.clipboard.writeText(url);
                      alert(`Invite link copied:\n${url}`);
                    }}
                    className="w-full py-2.5 px-4 rounded-xl bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-xs font-semibold text-[#00CBA0]"
                  >
                    Copy Sarvagyan Web Link
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: DIAGNOSTICS */}
          {activeTab === "diagnostics" && (
            <div className="glow-card p-6 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/60 space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-[#1E4D53]/40">
                <div>
                  <h3 className="text-base font-bold text-[#F5F7F2]">
                    Gnani & Backend Health Diagnostics
                  </h3>
                  <p className="text-xs text-[#A9BFBA]">
                    Live verification of Speech-to-Text, Machine Translation, and Neural Voice Synthesis.
                  </p>
                </div>
                <button
                  onClick={runDiagnostics}
                  disabled={diagLoading}
                  className="px-4 py-2 rounded-xl glow-button text-xs font-bold disabled:opacity-50"
                >
                  {diagLoading ? "Testing Engines..." : "Run Test Now ⟳"}
                </button>
              </div>

              {diagResult ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/70">
                    <span className="text-xs font-mono uppercase text-[#A9BFBA] block mb-1">Gnani STT</span>
                    <span className="text-lg font-bold text-[#00F0A0] flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#00F0A0]" />
                      Active (v3 WebSocket)
                    </span>
                    <p className="text-[11px] text-[#A9BFBA] mt-2">
                      Live duplex 16kHz PCM stream ready.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/70">
                    <span className="text-xs font-mono uppercase text-[#A9BFBA] block mb-1">Translation Bridge</span>
                    <span className="text-lg font-bold text-[#F5B52E] flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#F5B52E]" />
                      MyMemory / Gemini
                    </span>
                    <p className="text-[11px] text-[#A9BFBA] mt-2">
                      10 Indian language pairs supported.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/70">
                    <span className="text-xs font-mono uppercase text-[#A9BFBA] block mb-1">Gnani TTS</span>
                    <span className="text-lg font-bold text-[#00CBA0] flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#00CBA0]" />
                      Connected (Timbre)
                    </span>
                    <p className="text-[11px] text-[#A9BFBA] mt-2">
                      16kHz neural voice stream generation.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-sm text-[#A9BFBA]">
                  Click &ldquo;Run Test Now&rdquo; to test live connections to the Render backend.
                </div>
              )}
            </div>
          )}

          {/* TAB 5: SETTINGS */}
          {activeTab === "settings" && (
            <div className="glow-card p-6 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/60 max-w-2xl space-y-6">
              <h3 className="text-base font-bold text-[#F5F7F2] pb-4 border-b border-[#1E4D53]/40">
                User Profile & Preferences
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-1">
                    Display Name
                  </label>
                  <input
                    type="text"
                    disabled
                    value={user.display_name}
                    className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm opacity-80"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-1">
                    Email
                  </label>
                  <input
                    type="text"
                    disabled
                    value={user.email || "No email"}
                    className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm opacity-80"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-1">
                    Primary Speaking Language
                  </label>
                  <select
                    value={callLang}
                    onChange={(e) => {
                      setCallLang(e.target.value);
                      const updated = { ...user, language: e.target.value };
                      setUser(updated);
                      localStorage.setItem("sarvagyan_user", JSON.stringify(updated));
                    }}
                    className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l.code} value={l.code} className="bg-[#071B20]">
                        {l.native} — {l.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="pt-4 border-t border-[#1E4D53]/40 flex justify-between items-center">
                <span className="text-xs text-[#A9BFBA]">
                  Sarvagyan v1.0.0 Web · Connected to Render Backend
                </span>
                <button
                  onClick={handleSignOut}
                  className="px-4 py-2 rounded-xl bg-[#C62845]/20 hover:bg-[#C62845]/40 text-xs font-bold text-[#F5F7F2] transition-colors"
                >
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#071B20] flex items-center justify-center text-[#A9BFBA] text-sm">
          Loading Sarvagyan...
        </div>
      }
    >
      <SarvagyanAppContent />
    </Suspense>
  );
}
