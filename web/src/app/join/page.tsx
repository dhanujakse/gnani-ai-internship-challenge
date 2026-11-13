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

interface Utterance {
  id: string;
  speakerId: string;
  original: string;
  translation?: string;
  stage: string;
  mine: boolean;
}

function JoinCallContent() {
  const searchParams = useSearchParams();
  const initialCode = searchParams.get("code") || "";

  const [code, setCode] = useState(initialCode.toUpperCase());
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("ta-IN");

  const [status, setStatus] = useState<"idle" | "joining" | "connected" | "ended" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [peerName, setPeerName] = useState<string | null>(null);
  const [peerLanguage, setPeerLanguage] = useState<string | null>(null);
  const [myUserId, setMyUserId] = useState<string | null>(null);

  const [turns, setTurns] = useState<Utterance[]>([]);
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [peerSpeaking, setPeerSpeaking] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const transcriptsEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (initialCode) {
      setCode(initialCode.toUpperCase());
    }
  }, [initialCode]);

  useEffect(() => {
    transcriptsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  useEffect(() => {
    return () => {
      endCall();
    };
  }, []);

  const toggleMute = () => {
    if (mediaStreamRef.current) {
      const tracks = mediaStreamRef.current.getAudioTracks();
      tracks.forEach((track) => {
        track.enabled = isMuted;
      });
      setIsMuted(!isMuted);
    }
  };

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
      console.error("Microphone access error:", err);
      setErrorMessage("Microphone permission denied. You can listen and read subtitles, but cannot speak.");
    }
  };

  const handleJoinCall = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanCode = code.trim().toUpperCase();
    if (!cleanCode || cleanCode.length < 4) {
      setErrorMessage("Please enter a valid call code.");
      return;
    }

    setStatus("joining");
    setErrorMessage("");

    try {
      // 1. Get Guest Demo Token
      const authRes = await fetch(`${SERVER_URL}/v1/auth/demo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: name.trim() || "Web Guest",
          language: language,
        }),
      });

      if (!authRes.ok) {
        throw new Error("Could not connect to Sarvagyan cloud.");
      }

      const authData = await authRes.json();
      const token = authData.token;
      const uid = authData.user?.id;
      setMyUserId(uid);

      // 2. Join Call
      const joinRes = await fetch(`${SERVER_URL}/v1/calls/join`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          code: cleanCode,
          language: language,
        }),
      });

      if (!joinRes.ok) {
        const err = await joinRes.json().catch(() => ({}));
        throw new Error(err.detail || "Call not found. Check your invite code.");
      }

      const callData = await joinRes.json();
      const callId = callData.call_id;

      // 3. Connect to WebSocket
      const ws = new WebSocket(`${WS_URL}/v1/calls/${callId}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            type: "hello",
            language: language,
          })
        );
      };

      ws.onmessage = async (event) => {
        if (typeof event.data === "string") {
          try {
            const msg = JSON.parse(event.data);
            handleServerMessage(msg, uid);
          } catch (e) {
            console.error("JSON parse error:", e);
          }
        } else if (event.data instanceof Blob) {
          playAudioChunk(event.data);
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
      };

      ws.onclose = () => {
        if (status === "connected") {
          setStatus("ended");
        }
      };

      await startMicrophone(ws);
      setStatus("connected");
    } catch (err: unknown) {
      console.error("Join error:", err);
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Failed to join call.");
    }
  };

  const handleServerMessage = (msg: Record<string, unknown>, myId: string) => {
    switch (msg.type) {
      case "joined":
      case "peer_joined": {
        const peer = (msg.peer as Record<string, unknown>) || {};
        if (peer.name) {
          setPeerName(String(peer.name));
        }
        if (peer.language) {
          setPeerLanguage(String(peer.language));
        }
        break;
      }
      case "speech_activity": {
        if (msg.speaker_id === myId) {
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
            mine: speakerId === myId,
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
        setErrorMessage("The other person has left the call.");
        setStatus("ended");
        break;
      }
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
    setStatus("ended");
  };

  const myLangObj = LANGUAGES.find((l) => l.code === language);
  const peerLangObj = LANGUAGES.find((l) => l.code === peerLanguage);

  return (
    <div className="min-h-screen bg-[#071B20] text-[#F5F7F2] flex flex-col justify-between selection:bg-[#00CBA0] selection:text-[#071B20]">
      {/* Top Navbar */}
      <header className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-4 flex items-center justify-between border-b border-[#1E4D53]/30">
        <Link href="/" className="flex items-center gap-3">
          <div className="relative w-9 h-9 rounded-xl overflow-hidden border border-[#00CBA0]/40">
            <Image src="/logo.png" alt="Sarvagyan" fill className="object-cover" />
          </div>
          <span className="font-bold tracking-tight text-lg text-[#F5F7F2]">Sarvagyan</span>
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-xs px-3 py-1 rounded-full bg-[#12363A] text-[#00CBA0] border border-[#1E4D53] font-mono">
            {status === "connected" ? `ROOM #${code}` : "WEB COMPANION"}
          </span>
          <a
            href="/Sarvagyan.apk"
            download
            className="hidden sm:inline-flex text-xs px-3 py-1 rounded-full bg-[#0B292E] text-[#A9BFBA] hover:text-[#00CBA0] border border-[#1E4D53] transition-colors"
          >
            Get Android App
          </a>
        </div>
      </header>

      {/* Main Container — Widescreen 16:9 Desktop Ratio */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-6 lg:px-12 py-8 flex flex-col justify-center">
        {status === "idle" || status === "joining" || status === "error" ? (
          /* Widescreen Setup Stage: 2-Column Responsive Layout */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center max-w-5xl mx-auto w-full">
            {/* Left Column: Visual Call Intro */}
            <div className="lg:col-span-5 flex flex-col justify-center">
              <div className="relative w-16 h-16 rounded-2xl overflow-hidden border border-[#00CBA0]/60 shadow-xl shadow-[#00CBA0]/20 mb-6">
                <Image src="/logo.png" alt="Sarvagyan" fill className="object-cover" priority />
              </div>
              <h1 className="text-3xl font-extrabold text-[#F5F7F2] tracking-tight">
                Join Translated Call
              </h1>
              <p className="mt-3 text-sm text-[#A9BFBA] leading-relaxed">
                Connect instantly from your desktop or mobile browser. Choose your preferred language, speak into your microphone, and hear the other person translated in real time.
              </p>
              <div className="mt-6 p-4 rounded-2xl bg-[#0B292E]/60 border border-[#1E4D53]/60 space-y-2 text-xs text-[#A9BFBA]">
                <div className="flex items-center gap-2">
                  <span className="text-[#00CBA0]">✓</span> No account or registration required
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[#00CBA0]">✓</span> Live dual-language subtitles on screen
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[#00CBA0]">✓</span> Full compatibility with the Android native app
                </div>
              </div>
            </div>

            {/* Right Column: Setup Form */}
            <div className="lg:col-span-7">
              <div className="glow-card p-8 rounded-3xl border border-[#1E4D53]/70 bg-[#0B292E]/70 backdrop-blur-md">
                {errorMessage && (
                  <div className="mb-6 p-4 rounded-xl bg-[#C62845]/20 border border-[#C62845]/40 text-[#F5F7F2] text-sm text-center">
                    {errorMessage}
                  </div>
                )}

                <form onSubmit={handleJoinCall} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#A9BFBA] mb-2">
                      6-Letter Call Invite Code
                    </label>
                    <input
                      type="text"
                      maxLength={6}
                      value={code}
                      onChange={(e) => setCode(e.target.value.toUpperCase())}
                      placeholder="e.g. ABCXYZ"
                      className="w-full px-4 py-3.5 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] tracking-widest text-center font-mono font-bold text-xl focus:outline-none focus:border-[#00CBA0]"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#A9BFBA] mb-2">
                      Your Name
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="What should the other person call you?"
                      className="w-full px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[#A9BFBA] mb-2">
                      Select Your Speaking Language
                    </label>
                    <select
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] text-sm focus:outline-none focus:border-[#00CBA0]"
                    >
                      {LANGUAGES.map((l) => (
                        <option key={l.code} value={l.code} className="bg-[#071B20] text-[#F5F7F2]">
                          {l.native} — {l.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    type="submit"
                    disabled={status === "joining"}
                    className="w-full mt-4 py-3.5 px-6 rounded-xl font-bold glow-button disabled:opacity-50 text-sm tracking-wide shadow-lg"
                  >
                    {status === "joining" ? "Connecting to Call..." : "Enter Call Room →"}
                  </button>
                </form>
              </div>
            </div>
          </div>
        ) : status === "connected" ? (
          /* Widescreen Live Call Stage: Desktop 2-Column Split (Meet / Zoom Ratio) */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full items-stretch">
            {/* Left Column (5 cols): Speakers Presence Stage & Call Controls */}
            <div className="lg:col-span-5 flex flex-col gap-4">
              {/* Remote Speaker Card (16:9 / 16:10 Ratio) */}
              <div className="relative rounded-3xl p-6 bg-gradient-to-br from-[#0B292E] to-[#071B20] border border-[#1E4D53] shadow-xl flex flex-col justify-between min-h-[220px]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${peerSpeaking ? "bg-[#00F0A0] animate-ping" : "bg-[#A9BFBA]"}`} />
                    <span className="text-xs font-mono uppercase tracking-wider text-[#A9BFBA]">
                      Remote Participant
                    </span>
                  </div>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#12363A] text-[#00CBA0] border border-[#1E4D53] font-semibold">
                    {peerLangObj ? `${peerLangObj.native} (${peerLangObj.name})` : "Listening"}
                  </span>
                </div>

                <div className="text-center my-auto py-4">
                  <div className="w-16 h-16 mx-auto rounded-full bg-[#12363A] border-2 border-[#00CBA0]/40 flex items-center justify-center text-xl font-bold text-[#00CBA0] shadow-lg">
                    {peerName ? peerName[0].toUpperCase() : "P"}
                  </div>
                  <h3 className="text-lg font-bold text-[#F5F7F2] mt-3">
                    {peerName || "Waiting for partner..."}
                  </h3>
                  <p className="text-xs text-[#A9BFBA] mt-0.5">
                    {peerSpeaking ? "Speaking now..." : "Listening"}
                  </p>
                </div>

                {/* Animated Speech Waveform */}
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

              {/* Local Speaker (You) Card */}
              <div className="relative rounded-3xl p-6 bg-[#0B292E]/70 border border-[#00CBA0]/30 shadow-xl flex flex-col justify-between min-h-[180px]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${isSpeaking ? "bg-[#00CBA0] animate-ping" : "bg-[#00CBA0]"}`} />
                    <span className="text-xs font-mono uppercase tracking-wider text-[#00CBA0]">
                      You ({name || "Web User"})
                    </span>
                  </div>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#071B20] text-[#00CBA0] border border-[#1E4D53] font-semibold">
                    {myLangObj?.native} ({myLangObj?.name})
                  </span>
                </div>

                <div className="flex items-center justify-between my-auto py-2">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-full bg-[#00CBA0]/20 border border-[#00CBA0]/60 flex items-center justify-center font-bold text-[#00CBA0]">
                      {name ? name[0].toUpperCase() : "Y"}
                    </div>
                    <div>
                      <span className="text-sm font-bold text-[#F5F7F2] block">{name || "You"}</span>
                      <span className="text-xs text-[#A9BFBA]">
                        {isMuted ? "Microphone muted" : isSpeaking ? "Speaking into mic..." : "Mic active"}
                      </span>
                    </div>
                  </div>

                  {isSpeaking && (
                    <div className="flex items-center gap-1">
                      <span className="w-1 h-3 bg-[#00CBA0] rounded-full animate-bounce [animation-delay:0ms]" />
                      <span className="w-1 h-5 bg-[#00CBA0] rounded-full animate-bounce [animation-delay:150ms]" />
                      <span className="w-1 h-3 bg-[#00CBA0] rounded-full animate-bounce [animation-delay:300ms]" />
                    </div>
                  )}
                </div>

                {/* Bottom Call Action Deck */}
                <div className="flex items-center gap-3 pt-3 border-t border-[#1E4D53]/40">
                  <button
                    onClick={toggleMute}
                    className={`flex-1 py-2.5 px-4 rounded-xl font-semibold text-xs transition-colors flex items-center justify-center gap-2 border ${
                      isMuted
                        ? "bg-[#C62845]/20 border-[#C62845] text-[#F5F7F2]"
                        : "bg-[#12363A] border-[#1E4D53] text-[#00CBA0] hover:bg-[#194449]"
                    }`}
                  >
                    {isMuted ? "Unmute Mic" : "Mute Mic"}
                  </button>
                  <button
                    onClick={endCall}
                    className="flex-1 py-2.5 px-4 rounded-xl font-semibold text-xs bg-[#C62845] hover:bg-[#C62845]/80 text-white transition-colors"
                  >
                    End Call
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column (7 cols): Live Synchronized Bilingual Subtitle Studio */}
            <div className="lg:col-span-7 flex flex-col rounded-3xl glow-card border border-[#1E4D53]/70 bg-[#0B292E]/60 backdrop-blur-md overflow-hidden min-h-[460px] lg:min-h-[500px]">
              {/* Studio Header */}
              <div className="px-6 py-4 border-b border-[#1E4D53]/40 flex items-center justify-between bg-[#071B20]/60">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#00CBA0]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-[#F5F7F2]">
                    Real-Time Subtitles & Translation
                  </span>
                </div>
                <span className="text-[11px] font-mono text-[#A9BFBA]">
                  Gnani Neural Pipeline
                </span>
              </div>

              {/* Subtitles Transcript Feed */}
              <div className="flex-1 p-6 overflow-y-auto space-y-4 max-h-[520px]">
                {turns.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center text-[#A9BFBA] py-16 space-y-2">
                    <div className="w-12 h-12 rounded-2xl bg-[#12363A] border border-[#1E4D53] flex items-center justify-center text-[#00CBA0]">
                      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                      </svg>
                    </div>
                    <p className="text-sm font-semibold text-[#F5F7F2]">Waiting for speech...</p>
                    <p className="text-xs max-w-sm">
                      Start speaking naturally. Original speech and translated sentences will appear here in real-time.
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
                        <div className="mt-2 pt-2 border-t border-white/10 text-xs text-[#00F0A0] font-sans">
                          <span className="text-[10px] uppercase font-mono text-[#A9BFBA] mr-1 block">
                            {turn.mine ? "Translated to them:" : "Translated to you:"}
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
        ) : (
          /* Call Ended Screen */
          <div className="max-w-md mx-auto glow-card p-8 rounded-3xl text-center space-y-4">
            <div className="w-14 h-14 mx-auto rounded-full bg-[#12363A] border border-[#1E4D53] flex items-center justify-center text-2xl">
              📞
            </div>
            <h2 className="text-2xl font-bold text-[#F5F7F2]">Call Finished</h2>
            <p className="text-sm text-[#A9BFBA]">
              {errorMessage || "Thank you for using Sarvagyan Multilingual Calling."}
            </p>
            <div className="pt-4 flex flex-col sm:flex-row gap-3 justify-center">
              <button
                onClick={() => {
                  setStatus("idle");
                  setTurns([]);
                  setErrorMessage("");
                }}
                className="px-6 py-3 rounded-xl glow-button font-bold text-sm"
              >
                Join Another Call
              </button>
              <Link
                href="/"
                className="px-6 py-3 rounded-xl bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-sm font-semibold text-[#F5F7F2] transition-colors"
              >
                Back to Home
              </Link>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-4 flex items-center justify-between border-t border-[#1E4D53]/30 text-xs text-[#A9BFBA]">
        <p>Sarvagyan Web Companion · Render Cloud WebSocket · Gnani AI</p>
        <Link href="/" className="hover:text-[#00CBA0] transition-colors">
          Home
        </Link>
      </footer>
    </div>
  );
}

export default function JoinCallPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#071B20] flex items-center justify-center text-[#A9BFBA] text-sm">
          Loading Call Room...
        </div>
      }
    >
      <JoinCallContent />
    </Suspense>
  );
}
