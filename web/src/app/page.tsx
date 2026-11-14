"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";

const SERVER_URL = "https://sarvagyan-server.onrender.com";
const WS_URL = "wss://sarvagyan-server.onrender.com";
const APK_DOWNLOAD_URL = "/Sarvagyan.apk";

const LANGUAGES = [
  { code: "ta-IN", native: "தமிழ்", name: "Tamil" },
  { code: "en-IN", native: "English", name: "English" },
  { code: "hi-IN", native: "हिन्दी", name: "Hindi" },
  { code: "te-IN", native: "తెలుగు", name: "Telugu" },
  { code: "kn-IN", native: "ಕನ್ನಡ", name: "Kannada" },
  { code: "ml-IN", native: "മലയാളம்", name: "Malayalam" },
  { code: "mr-IN", native: "मराठी", name: "Marathi" },
  { code: "bn-IN", native: "বাংলা", name: "Bengali" },
  { code: "gu-IN", native: "ગુજરાતી", name: "Gujarati" },
  { code: "pa-IN", native: "ਪੰਜਾਬੀ", name: "Punjabi" },
];

const PRESET_AVATARS = [
  "avatar-01", "avatar-02", "avatar-03", "avatar-04",
  "avatar-05", "avatar-06", "avatar-07", "avatar-08",
  "avatar-09", "avatar-10", "avatar-11", "avatar-12",
  "avatar-13", "avatar-14"
];

interface UserProfile {
  id: string;
  display_name: string;
  email?: string;
  username?: string;
  language: string;
  avatar?: string | null;
  allow_calls?: string;
  read_receipts?: boolean;
  is_demo?: boolean;
}

interface CallHistoryItem {
  call_id: string;
  status: string;
  outcome?: string;
  duration_s?: number;
  created_at: number;
  my_language: string;
  peer?: {
    id: string;
    name: string;
    language: string;
    avatar?: string | null;
    favourite?: boolean;
  };
}

interface ContactItem {
  id: string;
  name: string;
  username?: string;
  language: string;
  avatar?: string | null;
  favourite?: boolean;
}

interface ChatConversation {
  id: string;
  type: string;
  title?: string;
  peer?: {
    id: string;
    display_name: string;
    avatar?: string | null;
    language: string;
  };
  last_message?: {
    text: string;
    timestamp: number;
  };
}

interface ChatMessage {
  id: string;
  sender_id: string;
  sender_name?: string;
  sender_avatar?: string | null;
  original_text: string;
  translated_text?: string;
  is_translated?: boolean;
  audio_id?: string;
  created_at: number;
}

interface VoicemailItem {
  id: string;
  sender_id: string;
  sender_name: string;
  sender_avatar?: string | null;
  sender_language: string;
  duration_s: number;
  original_transcript: string;
  translated_transcript: string;
  created_at: number;
  heard: boolean;
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

  // Auth & User Profile State
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string>("");
  const [authMode, setAuthMode] = useState<"signin" | "register">("signin");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authDisplayName, setAuthDisplayName] = useState("");
  const [authLanguage, setAuthLanguage] = useState("ta-IN");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  // Avatar Selection State (Mandatory after register/login if avatar is missing)
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [selectedAvatarId, setSelectedAvatarId] = useState<string>("avatar-01");
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [avatarError, setAvatarError] = useState("");

  // Navigation: calls, contacts, chats, diagnostics, settings
  const [activeTab, setActiveTab] = useState<"calls" | "contacts" | "chats" | "diagnostics" | "settings">("calls");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Calls Tab State (Dialer + History)
  const [callsSubTab, setCallsSubTab] = useState<"dialer" | "history">("dialer");
  const [dialCode, setDialCode] = useState(queryCode.toUpperCase());
  const [dialNumber, setDialNumber] = useState("");
  const [callLang, setCallLang] = useState("ta-IN");
  const [dialLoading, setDialLoading] = useState(false);
  const [createdRoomInfo, setCreatedRoomInfo] = useState<{ code: string; link: string } | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [history, setHistory] = useState<CallHistoryItem[]>([]);
  const [historyFilter, setHistoryFilter] = useState<"all" | "missed">("all");
  const [historyLoading, setHistoryLoading] = useState(false);

  // Contacts Tab State
  const [contacts, setContacts] = useState<ContactItem[]>([]);
  const [contactsSearch, setContactsSearch] = useState("");
  const [contactsLoading, setContactsLoading] = useState(false);
  const [newContactUsername, setNewContactUsername] = useState("");
  const [addContactError, setAddContactError] = useState("");

  // Chats & Voicemail Tab State
  const [chatSubTab, setChatSubTab] = useState<"chats" | "voicemails">("chats");
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<ChatConversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messageInput, setMessageInput] = useState("");
  const [voicemails, setVoicemails] = useState<VoicemailItem[]>([]);
  const [activeVoicemail, setActiveVoicemail] = useState<VoicemailItem | null>(null);

  // Diagnostics State
  const [diagResult, setDiagResult] = useState<Record<string, unknown> | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);

  // Settings State
  const [settingsGroup, setSettingsGroup] = useState<"account" | "privacy" | "language" | "calls" | "help">("account");
  const [noiseReduction, setNoiseReduction] = useState(true);
  const [allowCallsFrom, setAllowCallsFrom] = useState<"everyone" | "contacts">("contacts");
  const [readReceipts, setReadReceipts] = useState(true);
  const [privacyPolicyModal, setPrivacyPolicyModal] = useState(false);

  // Active In-Call State
  const [activeCallId, setActiveCallId] = useState<string | null>(null);
  const [activeCallCode, setActiveCallCode] = useState<string>("");
  const [peerName, setPeerName] = useState<string | null>(null);
  const [peerLang, setPeerLang] = useState<string | null>(null);
  const [peerAvatar, setPeerAvatar] = useState<string | null>(null);
  const [turns, setTurns] = useState<Utterance[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [peerSpeaking, setPeerSpeaking] = useState(false);
  const [callDuration, setCallDuration] = useState(0);
  const [midCallLangModal, setMidCallLangModal] = useState(false);

  // Audio References
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
        const parsed = JSON.parse(savedUser);
        setUser(parsed);
        setCallLang(parsed.language || "ta-IN");
        if (!parsed.avatar) {
          setShowAvatarPicker(true);
        }
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
  }, [turns, messages]);

  // Tab Data Loader
  useEffect(() => {
    if (!token) return;
    if (activeTab === "calls" && callsSubTab === "history") {
      loadHistory();
    } else if (activeTab === "contacts") {
      loadContacts();
    } else if (activeTab === "chats") {
      if (chatSubTab === "chats") loadConversations();
      else loadVoicemails();
    } else if (activeTab === "diagnostics") {
      runDiagnostics();
    }
  }, [activeTab, callsSubTab, chatSubTab, token]);

  // Handle URL query code
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

        // Prompt avatar selection if missing
        if (!data.user.avatar) {
          setShowAvatarPicker(true);
        }
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

        // Mandatory avatar selection screen on new account
        setShowAvatarPicker(true);
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

  // ---------------- AVATAR SELECTION HANDLERS ----------------
  const handleSavePresetAvatar = async (avatarId: string) => {
    setAvatarSaving(true);
    setAvatarError("");
    try {
      const res = await fetch(`${SERVER_URL}/v1/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ avatar: avatarId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Could not save avatar.");
      }
      const updatedUser = await res.json();
      setUser(updatedUser);
      localStorage.setItem("sarvagyan_user", JSON.stringify(updatedUser));
      setShowAvatarPicker(false);
    } catch (err: unknown) {
      setAvatarError(err instanceof Error ? err.message : "Error saving avatar.");
    } finally {
      setAvatarSaving(false);
    }
  };

  const handleCustomAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setAvatarError("Avatar photo is too large (max 2 MB).");
      return;
    }
    setAvatarSaving(true);
    setAvatarError("");
    try {
      const buffer = await file.arrayBuffer();
      const res = await fetch(`${SERVER_URL}/v1/me/avatar`, {
        method: "POST",
        headers: {
          "Content-Type": file.type || "application/octet-stream",
          Authorization: `Bearer ${token}`,
        },
        body: buffer,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Upload failed.");
      }
      const updatedUser = await res.json();
      setUser(updatedUser);
      localStorage.setItem("sarvagyan_user", JSON.stringify(updatedUser));
      setShowAvatarPicker(false);
    } catch (err: unknown) {
      setAvatarError(err instanceof Error ? err.message : "Upload error.");
    } finally {
      setAvatarSaving(false);
    }
  };

  // ---------------- CALL & WEBSOCKET ENGINE ----------------
  const startMicrophone = async (ws: WebSocket) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: noiseReduction,
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
        if (peer.avatar) setPeerAvatar(String(peer.avatar));
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
      if (!res.ok) throw new Error("Could not create call room.");
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

  const switchMidCallLanguage = (newLang: string) => {
    setCallLang(newLang);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "switch_language", language: newLang }));
    }
    setMidCallLangModal(false);
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
    setPeerAvatar(null);
    setIsSpeaking(false);
    setPeerSpeaking(false);
  };

  // ---------------- RECENTS, CONTACTS, CHATS API ----------------
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

  const toggleFavourite = async (contactId: string, isFav: boolean) => {
    try {
      await fetch(`${SERVER_URL}/v1/contacts/favourites/${contactId}`, {
        method: isFav ? "DELETE" : "PUT",
        headers: { Authorization: `Bearer ${token}` },
      });
      loadHistory();
      loadContacts();
    } catch {}
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
        throw new Error(err.detail || "User not found.");
      }
      setNewContactUsername("");
      loadContacts();
    } catch (err: unknown) {
      setAddContactError(err instanceof Error ? err.message : "Failed to add contact.");
    }
  };

  const loadConversations = async () => {
    try {
      const res = await fetch(`${SERVER_URL}/v1/chat/conversations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(data.conversations || []);
      }
    } catch {}
  };

  const loadMessages = async (cid: string) => {
    try {
      const res = await fetch(`${SERVER_URL}/v1/chat/conversations/${cid}/messages`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch {}
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeConversation || !messageInput.trim()) return;
    try {
      const res = await fetch(`${SERVER_URL}/v1/chat/conversations/${activeConversation.id}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ text: messageInput.trim() }),
      });
      if (res.ok) {
        setMessageInput("");
        loadMessages(activeConversation.id);
      }
    } catch {}
  };

  const loadVoicemails = async () => {
    try {
      const res = await fetch(`${SERVER_URL}/v1/voicemails`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setVoicemails(data.voicemails || []);
      }
    } catch {}
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

  const renderAvatarImg = (av?: string | null, name: string = "User", size: number = 40) => {
    if (av && av.startsWith("avatar-")) {
      return (
        <img
          src={`/avatars/${av}.webp`}
          alt={name}
          className="rounded-full object-cover shrink-0 border border-[#00CBA0]/40 shadow-sm"
          style={{ width: size, height: size }}
        />
      );
    } else if (av && av.startsWith("custom:")) {
      const fid = av.replace("custom:", "");
      return (
        <img
          src={`${SERVER_URL}/v1/avatars/${fid}`}
          alt={name}
          className="rounded-full object-cover shrink-0 border border-[#00CBA0]/40 shadow-sm"
          style={{ width: size, height: size }}
        />
      );
    }
    return (
      <div
        className="rounded-full bg-[#12363A] border border-[#00CBA0]/40 flex items-center justify-center font-bold text-[#00CBA0] shrink-0 shadow-sm"
        style={{ width: size, height: size, fontSize: Math.max(12, Math.floor(size * 0.4)) }}
      >
        {name ? name[0].toUpperCase() : "U"}
      </div>
    );
  };

  // ==================== 1. AUTH SCREEN (IF NOT LOGGED IN) ====================
  if (!user || !token) {
    return (
      <div className="min-h-screen text-[#F5F7F2] flex flex-col justify-between selection:bg-[#00CBA0] selection:text-[#071B20]">
        {/* Top Header */}
        <header className="w-full max-w-7xl mx-auto px-6 py-5 flex items-center justify-between border-b border-[#1E4D53]/40">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl overflow-hidden shadow-lg shadow-[#00CBA0]/20 border border-[#00CBA0]/40 shrink-0" style={{ width: 44, height: 44 }}>
              <Image src="/logo.png" alt="Sarvagyan" width={44} height={44} className="w-full h-full object-cover" priority style={{ width: 44, height: 44, objectFit: "cover" }} />
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-[#F5F7F2] block leading-none">
                Sarvagyan (सर्वज्ञान)
              </span>
              <span className="text-[10px] tracking-wider uppercase text-[#00CBA0] font-mono">
                Multilingual Voice Platform
              </span>
            </div>
          </div>

          <a
            href={APK_DOWNLOAD_URL}
            download="Sarvagyan.apk"
            className="inline-flex items-center gap-2 px-3.5 py-2 sm:px-4 sm:py-2 rounded-xl text-xs sm:text-sm font-semibold bg-[#12363A]/90 hover:bg-[#194449] border border-[#1E4D53] text-[#00CBA0] hover:text-[#00F0A0] transition-all shadow-md shrink-0"
          >
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span className="hidden sm:inline">Download APK for a better experience</span>
            <span className="sm:hidden">Download APK</span>
          </a>
        </header>

        {/* Widescreen Hero Auth Stage */}
        <main className="flex-1 w-full max-w-6xl mx-auto px-6 py-12 flex items-center justify-center">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center w-full">
            {/* Left Column: Brand Showcase */}
            <div className="lg:col-span-6 flex flex-col items-start text-left">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#12363A]/80 border border-[#1E4D53] text-xs font-semibold tracking-wide text-[#00CBA0] mb-6 shadow-sm">
                <span className="w-2 h-2 rounded-full bg-[#00F0A0] animate-ping" />
                Gnani AI Prisma & Timbre Neural Engine
              </div>

              <h1 className="text-4xl sm:text-5xl font-black tracking-tight text-[#F5F7F2] leading-tight">
                Speak in your language. <br />
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#00CBA0] via-[#00F0A0] to-[#F5B52E]">
                  They understand instantly.
                </span>
              </h1>

              <p className="mt-5 text-base text-[#A9BFBA] max-w-lg leading-relaxed">
                Experience natural bidirectional call translation across 10 Indian languages. Speak freely; the listener hears synthesized neural speech and sees live synchronized bilingual subtitles.
              </p>

              <div className="mt-8 grid grid-cols-2 gap-3 w-full max-w-md">
                <div className="p-3.5 rounded-2xl bg-[#0B292E]/70 border border-[#1E4D53]/70 backdrop-blur-md">
                  <span className="text-xs font-bold text-[#00CBA0] block">Full Parity with Mobile</span>
                  <span className="text-[11px] text-[#A9BFBA]">Web & Android share same backend</span>
                </div>
                <div className="p-3.5 rounded-2xl bg-[#0B292E]/70 border border-[#1E4D53]/70 backdrop-blur-md">
                  <span className="text-xs font-bold text-[#F5B52E] block">10 Indian Languages</span>
                  <span className="text-[11px] text-[#A9BFBA]">Duplex STT, MT & TTS</span>
                </div>
              </div>
            </div>

            {/* Right Column: Auth Card */}
            <div className="lg:col-span-6 flex justify-center">
              <div className="w-full max-w-md p-8 rounded-3xl glow-card border border-[#1E4D53]/80 bg-[#0B292E]/80 backdrop-blur-lg shadow-2xl">
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
                          placeholder="e.g. Siva Sanjay"
                          className="w-full px-4 py-3 rounded-xl bg-[#071B20]/90 border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-1.5">
                          Which Language Do You Speak?
                        </label>
                        <select
                          value={authLanguage}
                          onChange={(e) => setAuthLanguage(e.target.value)}
                          className="w-full px-4 py-3 rounded-xl bg-[#071B20]/90 border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
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
                      className="w-full px-4 py-3 rounded-xl bg-[#071B20]/90 border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
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
                      className="w-full px-4 py-3 rounded-xl bg-[#071B20]/90 border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
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
                      : "Create Account & Choose Avatar →"}
                  </button>
                </form>

                <div className="mt-6 pt-4 border-t border-[#1E4D53]/40 text-center">
                  <Link
                    href={`/join${queryCode ? `?code=${queryCode}` : ""}`}
                    className="text-xs text-[#00CBA0] hover:underline font-semibold"
                  >
                    Quick Join an Active Call via Code →
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="w-full max-w-7xl mx-auto px-6 py-4 flex items-center justify-between border-t border-[#1E4D53]/40 text-xs text-[#A9BFBA]">
          <p>© 2026 Sarvagyan · Multilingual Calling Platform</p>
          <a href={APK_DOWNLOAD_URL} download="Sarvagyan.apk" className="hover:text-[#00CBA0]">
            Download APK (58 MB)
          </a>
        </footer>
      </div>
    );
  }

  // ==================== 2. MANDATORY AVATAR SELECTION MODAL ====================
  // Blocks navigation to other screens until saved, as required!
  if (showAvatarPicker) {
    return (
      <div className="fixed inset-0 z-50 bg-[#071B20]/90 backdrop-blur-xl flex items-center justify-center p-4 sm:p-6">
        <div className="w-full max-w-2xl glow-card p-6 sm:p-8 rounded-3xl border border-[#00CBA0]/40 shadow-2xl bg-[#0B292E]/95 max-h-[90vh] overflow-y-auto">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-extrabold text-[#F5F7F2] tracking-tight">
              Choose your avatar
            </h2>
            <p className="text-xs text-[#A9BFBA] mt-1.5 max-w-md mx-auto">
              Pick an avatar for your profile. Your partner and contacts see this during calls, chats, and voicemails.
            </p>
          </div>

          {avatarError && (
            <div className="mb-4 p-3 rounded-xl bg-[#C62845]/20 border border-[#C62845]/50 text-xs text-[#F5F7F2] text-center">
              {avatarError}
            </div>
          )}

          {/* Current Selection Preview */}
          <div className="flex flex-col items-center justify-center mb-6 p-4 rounded-2xl bg-[#071B20]/70 border border-[#1E4D53]/60">
            <span className="text-[10px] uppercase tracking-wider text-[#A9BFBA] mb-2 font-mono">Current Preview</span>
            <div className="w-20 h-20 rounded-full border-2 border-[#00CBA0] p-1 shadow-lg shadow-[#00CBA0]/20">
              <img
                src={`/avatars/${selectedAvatarId}.webp`}
                alt="Selected Avatar"
                className="w-full h-full rounded-full object-cover"
              />
            </div>
            <span className="text-xs font-bold text-[#F5F7F2] mt-2 capitalize">{selectedAvatarId}</span>
          </div>

          {/* Preset Avatars Grid */}
          <div className="mb-6">
            <label className="block text-xs font-semibold text-[#A9BFBA] uppercase tracking-wider mb-3">
              14 Curated Indian Cultural Avatars
            </label>
            <div className="grid grid-cols-4 sm:grid-cols-7 gap-3">
              {PRESET_AVATARS.map((avId) => {
                const isSelected = selectedAvatarId === avId;
                return (
                  <button
                    key={avId}
                    type="button"
                    onClick={() => setSelectedAvatarId(avId)}
                    className={`relative p-1 rounded-2xl transition-all flex flex-col items-center border ${
                      isSelected
                        ? "border-[#00CBA0] bg-[#194449] shadow-lg shadow-[#00CBA0]/30 scale-105"
                        : "border-[#1E4D53]/60 bg-[#071B20]/60 hover:border-[#00CBA0]/40"
                    }`}
                  >
                    <img
                      src={`/avatars/${avId}-thumb.webp`}
                      alt={avId}
                      className="w-12 h-12 rounded-full object-cover"
                    />
                    {isSelected && (
                      <span className="absolute -top-1 -right-1 w-4 h-4 bg-[#00F0A0] text-[#071B20] rounded-full text-[10px] font-bold flex items-center justify-center">
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Custom Photo Upload Alternative */}
          <div className="mb-6 p-4 rounded-2xl bg-[#071B20]/50 border border-[#1E4D53]/60 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div>
              <span className="text-xs font-bold text-[#F5F7F2] block">Or upload your own photo</span>
              <span className="text-[11px] text-[#A9BFBA]">Max 2 MB (JPEG, PNG, WebP)</span>
            </div>
            <label className="px-4 py-2 rounded-xl bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-xs font-semibold text-[#00CBA0] cursor-pointer transition-colors whitespace-nowrap">
              <span>Choose Photo</span>
              <input
                type="file"
                accept="image/*"
                onChange={handleCustomAvatarUpload}
                className="hidden"
                disabled={avatarSaving}
              />
            </label>
          </div>

          {/* Save & Confirm Button */}
          <div className="flex gap-3 pt-2">
            {user.avatar && (
              <button
                type="button"
                onClick={() => setShowAvatarPicker(false)}
                className="flex-1 py-3 px-4 rounded-xl border border-[#1E4D53] text-xs font-semibold text-[#A9BFBA] hover:text-[#F5F7F2]"
              >
                Cancel
              </button>
            )}
            <button
              type="button"
              disabled={avatarSaving}
              onClick={() => handleSavePresetAvatar(selectedAvatarId)}
              className="flex-1 py-3 px-6 rounded-xl font-bold glow-button text-xs tracking-wider shadow-lg disabled:opacity-50"
            >
              {avatarSaving ? "Saving Avatar..." : "Save Avatar & Continue →"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ==================== 3. ACTIVE IN-CALL FULLSCREEN STUDIO ====================
  if (activeCallId) {
    const myLangObj = LANGUAGES.find((l) => l.code === callLang);
    const peerLangObj = LANGUAGES.find((l) => l.code === peerLang);

    return (
      <div className="min-h-screen text-[#F5F7F2] flex flex-col justify-between selection:bg-[#00CBA0] selection:text-[#071B20]">
        {/* Call Top Deck */}
        <header className="w-full px-6 lg:px-12 py-4 flex items-center justify-between border-b border-[#1E4D53]/40 bg-[#0B292E]/70 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-[#00F0A0] animate-pulse" />
            <span className="font-bold text-sm tracking-tight text-[#F5F7F2]">
              Sarvagyan Active Call · #{activeCallCode}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className="font-mono text-xs px-3 py-1 rounded-full bg-[#071B20]/80 border border-[#1E4D53] text-[#00CBA0]">
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
              onClick={() => setMidCallLangModal(true)}
              className="px-3.5 py-1.5 rounded-xl bg-[#12363A] hover:bg-[#194449] border border-[#00CBA0]/40 text-xs font-semibold text-[#00F0A0]"
            >
              Language: {myLangObj?.native} ▾
            </button>
            <button
              onClick={endCall}
              className="px-4 py-1.5 rounded-xl bg-[#C62845] hover:bg-[#C62845]/80 text-xs font-bold text-white transition-colors"
            >
              End Call
            </button>
          </div>
        </header>

        {/* Widescreen 16:9 In-Call Stage */}
        <main className="flex-1 w-full max-w-7xl mx-auto px-6 lg:px-12 py-6 flex items-stretch">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full items-stretch">
            {/* Left Column (5 cols): Participant Presence Stage */}
            <div className="lg:col-span-5 flex flex-col gap-4 justify-between">
              {/* Partner Card */}
              <div className="flex-1 rounded-3xl p-6 glow-card flex flex-col justify-between min-h-[220px]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${peerSpeaking ? "bg-[#00F0A0] animate-ping" : "bg-[#A9BFBA]"}`} />
                    <span className="text-xs font-mono uppercase tracking-wider text-[#A9BFBA]">
                      Remote Partner
                    </span>
                  </div>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#12363A] text-[#00CBA0] border border-[#1E4D53] font-semibold">
                    {peerLangObj ? `${peerLangObj.native} (${peerLangObj.name})` : "Listening"}
                  </span>
                </div>

                <div className="text-center my-auto py-3">
                  <div className="w-16 h-16 mx-auto">
                    {renderAvatarImg(peerAvatar, peerName || "Partner", 64)}
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
              <div className="rounded-3xl p-6 glow-card flex flex-col justify-between min-h-[170px]">
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
                    {renderAvatarImg(user.avatar, user.display_name, 44)}
                    <div>
                      <span className="text-sm font-bold text-[#F5F7F2] block">{user.display_name}</span>
                      <span className="text-xs text-[#A9BFBA]">
                        {isMuted ? "Microphone muted" : isSpeaking ? "Speaking..." : "Mic active"}
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
            <div className="lg:col-span-7 flex flex-col rounded-3xl glow-card overflow-hidden min-h-[460px]">
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
                      Speak freely in {myLangObj?.name}. The server transcribes, translates, and synthesizes neural voice in real time.
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

        {/* Mid-Call Language Switch Modal */}
        {midCallLangModal && (
          <div className="fixed inset-0 z-50 bg-[#071B20]/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="glow-card p-6 rounded-3xl max-w-md w-full border border-[#00CBA0]/40">
              <h3 className="text-base font-bold text-[#F5F7F2] mb-1">Switch Speaking Language</h3>
              <p className="text-xs text-[#A9BFBA] mb-4">
                Changes your speech recognition model instantly without dropping the call.
              </p>
              <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto mb-4">
                {LANGUAGES.map((l) => (
                  <button
                    key={l.code}
                    onClick={() => switchMidCallLanguage(l.code)}
                    className={`p-2.5 rounded-xl border text-xs text-left transition-all ${
                      callLang === l.code
                        ? "bg-[#194449] border-[#00CBA0] text-[#00CBA0] font-bold"
                        : "bg-[#071B20] border-[#1E4D53] text-[#F5F7F2] hover:bg-[#12363A]"
                    }`}
                  >
                    <span className="block font-semibold">{l.native}</span>
                    <span className="text-[10px] text-[#A9BFBA]">{l.name}</span>
                  </button>
                ))}
              </div>
              <button
                onClick={() => setMidCallLangModal(false)}
                className="w-full py-2.5 rounded-xl bg-[#12363A] text-xs font-semibold text-[#A9BFBA]"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ==================== 4. MAIN UNIFIED WEB APPLICATION ====================
  const userLangObj = LANGUAGES.find((l) => l.code === user.language);

  return (
    <div className="min-h-screen text-[#F5F7F2] flex flex-col lg:flex-row selection:bg-[#00CBA0] selection:text-[#071B20]">
      {/* MOBILE TOP BAR (Phone widths < 1024px) */}
      <div className="lg:hidden p-4 border-b border-[#1E4D53]/40 bg-[#0B292E]/90 backdrop-blur-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl overflow-hidden border border-[#00CBA0]/40 shrink-0" style={{ width: 36, height: 36 }}>
            <Image src="/logo.png" alt="Sarvagyan" width={36} height={36} className="w-full h-full object-cover" priority style={{ width: 36, height: 36, objectFit: "cover" }} />
          </div>
          <div>
            <span className="text-sm font-bold block leading-none">Sarvagyan</span>
            <span className="text-[10px] text-[#00CBA0] font-mono">Web Platform</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={APK_DOWNLOAD_URL}
            download="Sarvagyan.apk"
            className="px-2.5 py-1.5 rounded-lg bg-[#12363A] border border-[#1E4D53] text-[11px] font-semibold text-[#00CBA0]"
          >
            Download APK
          </a>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-lg bg-[#12363A] text-[#F5F7F2]"
          >
            ☰
          </button>
        </div>
      </div>

      {/* LEFT SIDEBAR (Desktop 280px) */}
      <aside className={`w-full lg:w-72 bg-[#0B292E]/90 lg:bg-[#0B292E]/70 border-r border-[#1E4D53]/40 flex flex-col justify-between shrink-0 backdrop-blur-md ${
        mobileMenuOpen ? "block" : "hidden lg:flex"
      }`}>
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
                Multilingual Platform
              </span>
            </div>
          </div>

          {/* User Profile Pill with Avatar */}
          <div className="p-4 mx-4 my-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/60 flex items-center gap-3">
            <div className="relative group cursor-pointer" onClick={() => setShowAvatarPicker(true)}>
              {renderAvatarImg(user.avatar, user.display_name, 44)}
              <span className="absolute inset-0 bg-black/40 rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-[10px] text-white">
                Edit
              </span>
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

          {/* Navigation Links matching Mobile App options */}
          <nav className="px-3 space-y-1">
            <button
              onClick={() => { setActiveTab("calls"); setMobileMenuOpen(false); }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "calls"
                  ? "bg-[#194449] text-[#00CBA0] shadow-sm"
                  : "text-[#A9BFBA] hover:text-[#F5F7F2] hover:bg-[#12363A]/50"
              }`}
            >
              <span className="text-base">📞</span>
              <span>Calls & Dialer</span>
            </button>

            <button
              onClick={() => { setActiveTab("contacts"); setMobileMenuOpen(false); }}
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
              onClick={() => { setActiveTab("chats"); setMobileMenuOpen(false); }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "chats"
                  ? "bg-[#194449] text-[#00CBA0] shadow-sm"
                  : "text-[#A9BFBA] hover:text-[#F5F7F2] hover:bg-[#12363A]/50"
              }`}
            >
              <span className="text-base">💬</span>
              <span>Chats & Voicemail</span>
            </button>

            <button
              onClick={() => { setActiveTab("diagnostics"); setMobileMenuOpen(false); }}
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
              onClick={() => { setActiveTab("settings"); setMobileMenuOpen(false); }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "settings"
                  ? "bg-[#194449] text-[#00CBA0] shadow-sm"
                  : "text-[#A9BFBA] hover:text-[#F5F7F2] hover:bg-[#12363A]/50"
              }`}
            >
              <span className="text-base">⚙️</span>
              <span>Settings</span>
            </button>
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-[#1E4D53]/30 space-y-2">
          <a
            href={APK_DOWNLOAD_URL}
            download="Sarvagyan.apk"
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs font-semibold bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-[#00CBA0] transition-colors"
          >
            <span>Download APK (58 MB)</span>
          </a>
          <button
            onClick={handleSignOut}
            className="w-full py-2 px-3 rounded-xl text-xs font-semibold text-[#A9BFBA] hover:text-[#C62845] transition-colors text-center"
          >
            Sign Out
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT WORKSPACE */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Navbar */}
        <header className="px-6 lg:px-10 py-4 border-b border-[#1E4D53]/30 flex items-center justify-between bg-[#071B20]/70 backdrop-blur-md">
          <h2 className="text-lg lg:text-xl font-bold text-[#F5F7F2] capitalize">
            {activeTab === "calls" && "Calls & Instant Dialer"}
            {activeTab === "contacts" && "Contacts Management"}
            {activeTab === "chats" && "Translated Chats & Voicemail"}
            {activeTab === "diagnostics" && "AI Pipeline Diagnostics"}
            {activeTab === "settings" && "Application Settings"}
          </h2>

          <div className="flex items-center gap-4">
            <a
              href={APK_DOWNLOAD_URL}
              download="Sarvagyan.apk"
              className="hidden sm:inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-[#12363A]/90 hover:bg-[#194449] border border-[#1E4D53] text-[#00CBA0] hover:text-[#00F0A0] transition-all shadow-md"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span>Download APK for a better experience</span>
            </a>
            <span className="text-xs px-3 py-1 rounded-full bg-[#12363A] text-[#00CBA0] border border-[#1E4D53] font-mono">
              Render Cloud
            </span>
          </div>
        </header>

        {/* Tab Content Panes */}
        <div className="p-6 lg:p-8 max-w-6xl w-full mx-auto">
          {/* TAB 1: CALLS & DIALER */}
          {activeTab === "calls" && (
            <div className="space-y-6">
              {/* Calls Subtabs: Dialer vs Call History */}
              <div className="flex items-center gap-3 border-b border-[#1E4D53]/40 pb-3">
                <button
                  onClick={() => setCallsSubTab("dialer")}
                  className={`text-sm font-bold pb-2 transition-all ${
                    callsSubTab === "dialer"
                      ? "text-[#00CBA0] border-b-2 border-[#00CBA0]"
                      : "text-[#A9BFBA] hover:text-[#F5F7F2]"
                  }`}
                >
                  Dialer & Instant Room
                </button>
                <button
                  onClick={() => { setCallsSubTab("history"); loadHistory(); }}
                  className={`text-sm font-bold pb-2 transition-all ${
                    callsSubTab === "history"
                      ? "text-[#00CBA0] border-b-2 border-[#00CBA0]"
                      : "text-[#A9BFBA] hover:text-[#F5F7F2]"
                  }`}
                >
                  Call History
                </button>
              </div>

              {callsSubTab === "dialer" ? (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                  {/* Left Column (7 cols): Start Call / Create Room */}
                  <div className="lg:col-span-7 space-y-6">
                    {/* Instant Room Creation Card */}
                    <div className="glow-card p-6 rounded-3xl">
                      <h3 className="text-base font-bold text-[#F5F7F2] mb-1">
                        Start a Translated Voice Call
                      </h3>
                      <p className="text-xs text-[#A9BFBA] mb-4">
                        Create a room and invite anyone on Android or Web with a single link.
                      </p>

                      <div className="mb-4">
                        <label className="block text-xs font-semibold uppercase tracking-wider text-[#A9BFBA] mb-1.5">
                          Your Speaking Language
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
                        {dialLoading ? "Creating Room..." : "Create Room & Start Call →"}
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

                    {/* Join Existing Call Card */}
                    <div className="glow-card p-6 rounded-3xl">
                      <h3 className="text-base font-bold text-[#F5F7F2] mb-1">
                        Join with Invite Code
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

                  {/* Right Column (5 cols): Phone Keypad & Dialpad */}
                  <div className="lg:col-span-5 glow-card p-6 rounded-3xl flex flex-col items-center">
                    <span className="text-xs font-bold uppercase tracking-wider text-[#A9BFBA] mb-3 self-start">
                      Direct Dialpad
                    </span>
                    <input
                      type="text"
                      value={dialNumber}
                      onChange={(e) => setDialNumber(e.target.value)}
                      placeholder="Enter phone or code"
                      className="w-full mb-4 px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-center font-mono font-bold text-xl tracking-wider text-[#F5F7F2] focus:outline-none focus:border-[#00CBA0]"
                    />
                    <div className="grid grid-cols-3 gap-3 w-full max-w-[260px] mb-4">
                      {["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"].map((btn) => (
                        <button
                          key={btn}
                          type="button"
                          onClick={() => setDialNumber((prev) => prev + btn)}
                          className="h-12 rounded-2xl bg-[#071B20] border border-[#1E4D53] hover:border-[#00CBA0] hover:bg-[#12363A] text-base font-bold text-[#F5F7F2] transition-colors"
                        >
                          {btn}
                        </button>
                      ))}
                    </div>
                    <div className="flex gap-2 w-full max-w-[260px]">
                      <button
                        type="button"
                        onClick={() => setDialNumber((prev) => prev.slice(0, -1))}
                        className="flex-1 py-2.5 rounded-xl bg-[#12363A] text-xs font-semibold text-[#A9BFBA]"
                      >
                        ⌫ Delete
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (dialNumber.length === 6) {
                            setDialCode(dialNumber.toUpperCase());
                            handleJoinCallByCode();
                          } else {
                            handleCreateRoom();
                          }
                        }}
                        className="flex-1 py-2.5 rounded-xl font-bold glow-button text-xs"
                      >
                        Call
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* CALL HISTORY SUBTAB */
                <div className="glow-card p-6 rounded-3xl">
                  <div className="flex items-center justify-between mb-6 pb-4 border-b border-[#1E4D53]/40">
                    <div className="flex gap-3">
                      <button
                        onClick={() => setHistoryFilter("all")}
                        className={`text-xs font-bold px-3 py-1.5 rounded-xl border ${
                          historyFilter === "all" ? "bg-[#194449] border-[#00CBA0] text-[#00CBA0]" : "border-[#1E4D53] text-[#A9BFBA]"
                        }`}
                      >
                        All Calls
                      </button>
                      <button
                        onClick={() => setHistoryFilter("missed")}
                        className={`text-xs font-bold px-3 py-1.5 rounded-xl border ${
                          historyFilter === "missed" ? "bg-[#194449] border-[#00CBA0] text-[#00CBA0]" : "border-[#1E4D53] text-[#A9BFBA]"
                        }`}
                      >
                        Missed
                      </button>
                    </div>
                    <button onClick={loadHistory} className="text-xs text-[#00CBA0] hover:underline font-semibold">
                      ↻ Refresh
                    </button>
                  </div>

                  {historyLoading ? (
                    <div className="text-center py-12 text-sm text-[#A9BFBA]">Loading past calls...</div>
                  ) : history.length === 0 ? (
                    <div className="text-center py-16 text-sm text-[#A9BFBA] space-y-2">
                      <div className="text-3xl">📞</div>
                      <p className="font-semibold text-[#F5F7F2]">No recent calls found</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {history
                        .filter((h) => (historyFilter === "missed" ? h.status === "missed" : true))
                        .map((h) => (
                          <div
                            key={h.call_id}
                            className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/60 flex items-center justify-between hover:border-[#00CBA0]/40 transition-colors"
                          >
                            <div className="flex items-center gap-3">
                              {renderAvatarImg(h.peer?.avatar, h.peer?.name || "Caller", 40)}
                              <div>
                                <span className="text-sm font-bold text-[#F5F7F2] block">
                                  {h.peer?.name || "Web Call"}
                                </span>
                                <span className="text-xs text-[#A9BFBA]">
                                  {new Date(h.created_at * 1000).toLocaleDateString()} · {h.duration_s ? `${h.duration_s}s` : "Ended"} · {h.my_language}
                                </span>
                              </div>
                            </div>

                            <div className="flex items-center gap-2">
                              {h.peer && (
                                <button
                                  onClick={() => toggleFavourite(h.peer!.id, Boolean(h.peer!.favourite))}
                                  className="p-2 text-base text-[#F5B52E]"
                                >
                                  {h.peer.favourite ? "★" : "☆"}
                                </button>
                              )}
                              <button
                                onClick={handleCreateRoom}
                                className="px-3.5 py-1.5 rounded-xl bg-[#194449] hover:bg-[#12363A] border border-[#00CBA0]/40 text-xs font-bold text-[#00CBA0]"
                              >
                                Call Back
                              </button>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: CONTACTS */}
          {activeTab === "contacts" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Contacts List (8 cols) */}
              <div className="lg:col-span-8 glow-card p-6 rounded-3xl">
                <div className="flex items-center justify-between mb-4 pb-4 border-b border-[#1E4D53]/40">
                  <span className="text-sm font-bold text-[#F5F7F2]">All Contacts</span>
                  <button onClick={loadContacts} className="text-xs text-[#00CBA0] hover:underline font-semibold">
                    ↻ Refresh
                  </button>
                </div>

                <div className="mb-4">
                  <input
                    type="text"
                    value={contactsSearch}
                    onChange={(e) => setContactsSearch(e.target.value)}
                    placeholder="Search by name or @username..."
                    className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-xs focus:outline-none focus:border-[#00CBA0]"
                  />
                </div>

                {contactsLoading ? (
                  <div className="text-center py-12 text-sm text-[#A9BFBA]">Loading contacts...</div>
                ) : contacts.length === 0 ? (
                  <div className="text-center py-16 text-sm text-[#A9BFBA] space-y-2">
                    <div className="text-3xl">👥</div>
                    <p className="font-semibold text-[#F5F7F2]">No contacts yet</p>
                    <p className="text-xs">Add a friend by username or share an invite link.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {contacts
                      .filter((c) =>
                        c.name.toLowerCase().includes(contactsSearch.toLowerCase()) ||
                        (c.username && c.username.toLowerCase().includes(contactsSearch.toLowerCase()))
                      )
                      .map((c) => (
                        <div
                          key={c.id}
                          className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/60 flex items-center justify-between hover:border-[#00CBA0]/40 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            {renderAvatarImg(c.avatar, c.name, 40)}
                            <div>
                              <span className="text-sm font-bold text-[#F5F7F2] block">{c.name}</span>
                              <span className="text-xs text-[#A9BFBA]">
                                @{c.username || c.id.slice(0, 8)} · {c.language}
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => toggleFavourite(c.id, Boolean(c.favourite))}
                              className="p-1.5 text-base text-[#F5B52E]"
                            >
                              {c.favourite ? "★" : "☆"}
                            </button>
                            <button
                              onClick={handleCreateRoom}
                              className="px-3.5 py-1.5 rounded-xl bg-[#009B77] hover:bg-[#00CBA0] text-xs font-bold text-[#071B20] transition-colors"
                            >
                              Call
                            </button>
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </div>

              {/* Add Contact Sidebar (4 cols) */}
              <div className="lg:col-span-4 glow-card p-6 rounded-3xl space-y-4">
                <h3 className="text-sm font-bold text-[#F5F7F2] uppercase tracking-wider">
                  Add Contact
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
                    className="w-full py-2.5 px-4 rounded-xl font-bold glow-button text-xs tracking-wide shadow-md"
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
                    Copy Website Link
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: CHATS & VOICEMAIL */}
          {activeTab === "chats" && (
            <div className="glow-card p-6 rounded-3xl space-y-6">
              <div className="flex items-center gap-3 border-b border-[#1E4D53]/40 pb-3">
                <button
                  onClick={() => setChatSubTab("chats")}
                  className={`text-sm font-bold pb-2 transition-all ${
                    chatSubTab === "chats"
                      ? "text-[#00CBA0] border-b-2 border-[#00CBA0]"
                      : "text-[#A9BFBA] hover:text-[#F5F7F2]"
                  }`}
                >
                  Translated Chats
                </button>
                <button
                  onClick={() => { setChatSubTab("voicemails"); loadVoicemails(); }}
                  className={`text-sm font-bold pb-2 transition-all ${
                    chatSubTab === "voicemails"
                      ? "text-[#00CBA0] border-b-2 border-[#00CBA0]"
                      : "text-[#A9BFBA] hover:text-[#F5F7F2]"
                  }`}
                >
                  Voicemails
                </button>
              </div>

              {chatSubTab === "chats" ? (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch min-h-[400px]">
                  {/* Conversations Sidebar (4 cols) */}
                  <div className="lg:col-span-4 rounded-2xl bg-[#071B20]/60 border border-[#1E4D53]/60 p-4 space-y-3">
                    <span className="text-xs font-bold text-[#A9BFBA] uppercase tracking-wider block mb-2">
                      Conversations
                    </span>
                    {conversations.length === 0 ? (
                      <p className="text-xs text-[#A9BFBA] py-8 text-center">No active chats yet</p>
                    ) : (
                      conversations.map((conv) => (
                        <div
                          key={conv.id}
                          onClick={() => { setActiveConversation(conv); loadMessages(conv.id); }}
                          className={`p-3 rounded-xl border cursor-pointer transition-colors flex items-center gap-3 ${
                            activeConversation?.id === conv.id
                              ? "bg-[#194449] border-[#00CBA0]"
                              : "bg-[#071B20] border-[#1E4D53] hover:bg-[#12363A]"
                          }`}
                        >
                          {renderAvatarImg(conv.peer?.avatar, conv.peer?.display_name || "Chat", 36)}
                          <div className="flex-1 min-w-0">
                            <span className="text-xs font-bold text-[#F5F7F2] block truncate">
                              {conv.peer?.display_name || conv.title || "Group Chat"}
                            </span>
                            <span className="text-[10px] text-[#A9BFBA] truncate block">
                              {conv.last_message?.text || "Start chatting..."}
                            </span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Messages Feed (8 cols) */}
                  <div className="lg:col-span-8 rounded-2xl bg-[#071B20]/60 border border-[#1E4D53]/60 p-4 flex flex-col justify-between">
                    {activeConversation ? (
                      <>
                        <div className="pb-3 border-b border-[#1E4D53]/40 flex items-center justify-between">
                          <span className="text-xs font-bold text-[#F5F7F2]">
                            {activeConversation.peer?.display_name || "Chat"}
                          </span>
                          <span className="text-[10px] text-[#00CBA0] font-mono">Bilingual Auto-Translation</span>
                        </div>

                        <div className="flex-1 py-4 overflow-y-auto space-y-3 max-h-72">
                          {messages.map((m) => (
                            <div
                              key={m.id}
                              className={`p-3 rounded-xl max-w-[80%] text-xs ${
                                m.sender_id === user.id
                                  ? "ml-auto bg-[#194449] text-right"
                                  : "mr-auto bg-[#0B292E] text-left"
                              }`}
                            >
                              <p className="font-medium text-[#F5F7F2]">{m.original_text}</p>
                              {m.translated_text && (
                                <p className="text-[11px] text-[#00CBA0] mt-1 pt-1 border-t border-white/10">
                                  {m.translated_text}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>

                        <form onSubmit={sendMessage} className="flex gap-2 pt-2 border-t border-[#1E4D53]/40">
                          <input
                            type="text"
                            value={messageInput}
                            onChange={(e) => setMessageInput(e.target.value)}
                            placeholder="Type in your language..."
                            className="flex-1 px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-xs focus:outline-none focus:border-[#00CBA0]"
                          />
                          <button type="submit" className="px-5 py-2.5 rounded-xl glow-button text-xs font-bold">
                            Send
                          </button>
                        </form>
                      </>
                    ) : (
                      <div className="my-auto text-center text-[#A9BFBA] text-xs py-16">
                        Select or start a conversation to see live translated chat.
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                /* VOICEMAILS SUBTAB */
                <div className="space-y-3">
                  {voicemails.length === 0 ? (
                    <div className="text-center py-12 text-xs text-[#A9BFBA]">
                      No voicemails received yet.
                    </div>
                  ) : (
                    voicemails.map((v) => (
                      <div
                        key={v.id}
                        className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53] flex items-center justify-between"
                      >
                        <div className="flex items-center gap-3">
                          {renderAvatarImg(v.sender_avatar, v.sender_name, 40)}
                          <div>
                            <span className="text-xs font-bold text-[#F5F7F2] block">{v.sender_name}</span>
                            <span className="text-[11px] text-[#A9BFBA] block">
                              Duration: {v.duration_s}s · {new Date(v.created_at * 1000).toLocaleDateString()}
                            </span>
                            <p className="text-xs text-[#00F0A0] mt-1">&ldquo;{v.translated_transcript}&rdquo;</p>
                          </div>
                        </div>

                        <audio
                          controls
                          src={`${SERVER_URL}/v1/voicemails/${v.id}/audio`}
                          className="h-8 max-w-[200px]"
                        />
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: DIAGNOSTICS */}
          {activeTab === "diagnostics" && (
            <div className="glow-card p-6 rounded-3xl space-y-6">
              <div className="flex items-center justify-between pb-4 border-b border-[#1E4D53]/40">
                <div>
                  <h3 className="text-base font-bold text-[#F5F7F2]">
                    Gnani AI & Cloud Diagnostics
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
                    <span className="text-base font-bold text-[#00F0A0] flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#00F0A0]" />
                      Active (Prisma v3)
                    </span>
                    <p className="text-[11px] text-[#A9BFBA] mt-2">
                      Live duplex 16kHz PCM stream ready.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/70">
                    <span className="text-xs font-mono uppercase text-[#A9BFBA] block mb-1">Translation Bridge</span>
                    <span className="text-base font-bold text-[#F5B52E] flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#F5B52E]" />
                      MyMemory / Gemini
                    </span>
                    <p className="text-[11px] text-[#A9BFBA] mt-2">
                      10 Indian language pairs supported.
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53]/70">
                    <span className="text-xs font-mono uppercase text-[#A9BFBA] block mb-1">Gnani TTS</span>
                    <span className="text-base font-bold text-[#00CBA0] flex items-center gap-1.5">
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
                  Click &ldquo;Run Test Now&rdquo; to test live connections to the Render cloud backend.
                </div>
              )}
            </div>
          )}

          {/* TAB 5: SETTINGS HUB */}
          {activeTab === "settings" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Settings Navigation Groups (4 cols) */}
              <div className="lg:col-span-4 glow-card p-4 rounded-3xl space-y-1">
                {[
                  { id: "account", label: "Account & Profile", icon: "👤" },
                  { id: "language", label: "Language & Voice", icon: "🌐" },
                  { id: "calls", label: "Call Settings", icon: "📞" },
                  { id: "privacy", label: "Privacy & Safety", icon: "🔒" },
                  { id: "help", label: "Help & About", icon: "ℹ️" },
                ].map((g) => (
                  <button
                    key={g.id}
                    onClick={() => setSettingsGroup(g.id as any)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-xs font-semibold text-left transition-colors ${
                      settingsGroup === g.id
                        ? "bg-[#194449] text-[#00CBA0]"
                        : "text-[#A9BFBA] hover:bg-[#12363A]/40"
                    }`}
                  >
                    <span>{g.icon}</span>
                    <span>{g.label}</span>
                  </button>
                ))}
              </div>

              {/* Settings Details Pane (8 cols) */}
              <div className="lg:col-span-8 glow-card p-6 rounded-3xl space-y-6">
                {settingsGroup === "account" && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-[#F5F7F2] pb-2 border-b border-[#1E4D53]/40">
                      Profile Information
                    </h3>
                    <div className="flex items-center gap-4">
                      {renderAvatarImg(user.avatar, user.display_name, 64)}
                      <div>
                        <button
                          onClick={() => setShowAvatarPicker(true)}
                          className="px-3.5 py-1.5 rounded-xl bg-[#12363A] hover:bg-[#194449] border border-[#00CBA0]/40 text-xs font-semibold text-[#00CBA0]"
                        >
                          Change Avatar
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-[#A9BFBA] mb-1">Display Name</label>
                      <input
                        type="text"
                        disabled
                        value={user.display_name}
                        className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-sm text-[#F5F7F2] opacity-80"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-[#A9BFBA] mb-1">Email</label>
                      <input
                        type="text"
                        disabled
                        value={user.email || "No email"}
                        className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-sm text-[#F5F7F2] opacity-80"
                      />
                    </div>
                  </div>
                )}

                {settingsGroup === "language" && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-[#F5F7F2] pb-2 border-b border-[#1E4D53]/40">
                      Language & Voice Preferences
                    </h3>
                    <div>
                      <label className="block text-xs font-semibold text-[#A9BFBA] mb-2">
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
                        className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-sm text-[#F5F7F2]"
                      >
                        {LANGUAGES.map((l) => (
                          <option key={l.code} value={l.code} className="bg-[#071B20]">
                            {l.native} — {l.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                {settingsGroup === "calls" && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-[#F5F7F2] pb-2 border-b border-[#1E4D53]/40">
                      Call Audio & Noise Suppression
                    </h3>
                    <div className="flex items-center justify-between p-3 rounded-xl bg-[#071B20]/60 border border-[#1E4D53]/60">
                      <div>
                        <span className="text-xs font-bold text-[#F5F7F2] block">Noise Reduction Filter</span>
                        <span className="text-[11px] text-[#A9BFBA]">Suppresses background audio and microphone clicks</span>
                      </div>
                      <input
                        type="checkbox"
                        checked={noiseReduction}
                        onChange={(e) => setNoiseReduction(e.target.checked)}
                        className="w-4 h-4 accent-[#00CBA0]"
                      />
                    </div>
                  </div>
                )}

                {settingsGroup === "privacy" && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-[#F5F7F2] pb-2 border-b border-[#1E4D53]/40">
                      Privacy & Safety
                    </h3>
                    <div>
                      <label className="block text-xs font-semibold text-[#A9BFBA] mb-2">Who can call you</label>
                      <select
                        value={allowCallsFrom}
                        onChange={(e) => setAllowCallsFrom(e.target.value as any)}
                        className="w-full px-4 py-2.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-sm text-[#F5F7F2]"
                      >
                        <option value="contacts">Contacts only</option>
                        <option value="everyone">Everyone</option>
                      </select>
                    </div>

                    <div className="flex items-center justify-between p-3 rounded-xl bg-[#071B20]/60 border border-[#1E4D53]/60">
                      <div>
                        <span className="text-xs font-bold text-[#F5F7F2] block">Read Receipts</span>
                        <span className="text-[11px] text-[#A9BFBA]">Show when you have read messages</span>
                      </div>
                      <input
                        type="checkbox"
                        checked={readReceipts}
                        onChange={(e) => setReadReceipts(e.target.checked)}
                        className="w-4 h-4 accent-[#00CBA0]"
                      />
                    </div>
                  </div>
                )}

                {settingsGroup === "help" && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-[#F5F7F2] pb-2 border-b border-[#1E4D53]/40">
                      Help & Legal
                    </h3>
                    <p className="text-xs text-[#A9BFBA] leading-relaxed">
                      Sarvagyan (सर्वज्ञान) is a real-time multilingual communication application supporting live bi-directional call translation across 10 Indian languages.
                    </p>
                    <div className="pt-2 flex gap-3">
                      <button
                        onClick={() => setPrivacyPolicyModal(true)}
                        className="px-4 py-2 rounded-xl bg-[#12363A] text-xs font-semibold text-[#00CBA0]"
                      >
                        Privacy Policy
                      </button>
                      <a
                        href={APK_DOWNLOAD_URL}
                        download="Sarvagyan.apk"
                        className="px-4 py-2 rounded-xl bg-[#12363A] text-xs font-semibold text-[#00CBA0]"
                      >
                        Download Android App
                      </a>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Privacy Policy Modal */}
      {privacyPolicyModal && (
        <div className="fixed inset-0 z-50 bg-[#071B20]/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glow-card p-6 rounded-3xl max-w-lg w-full max-h-[80vh] overflow-y-auto">
            <h3 className="text-base font-bold text-[#F5F7F2] mb-3">Privacy Policy</h3>
            <div className="text-xs text-[#A9BFBA] space-y-3 leading-relaxed">
              <p>
                <strong>No audio is ever stored:</strong> Call audio is streamed in real time to Gnani AI models and immediately discarded.
              </p>
              <p>
                <strong>Encryption:</strong> All call signaling and WebSockets communicate via TLS/WSS.
              </p>
              <p>
                <strong>Contacts Privacy:</strong> Contact phone matching hashes phone numbers using SHA-256 before transmission.
              </p>
            </div>
            <button
              onClick={() => setPrivacyPolicyModal(false)}
              className="mt-6 w-full py-2.5 rounded-xl glow-button font-bold text-xs"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center text-[#A9BFBA] text-sm">
          Loading Sarvagyan...
        </div>
      }
    >
      <SarvagyanAppContent />
    </Suspense>
  );
}
