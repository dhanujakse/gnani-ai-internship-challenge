"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

const LANGUAGES = [
  { code: "ta-IN", native: "தமிழ்", name: "Tamil", tag: "Primary" },
  { code: "en-IN", native: "English", name: "English", tag: "Global" },
  { code: "hi-IN", native: "हिन्दी", name: "Hindi", tag: "Popular" },
  { code: "te-IN", native: "తెలుగు", name: "Telugu", tag: "Popular" },
  { code: "kn-IN", native: "ಕನ್ನಡ", name: "Kannada", tag: "Popular" },
  { code: "ml-IN", native: "മലയാളം", name: "Malayalam", tag: "Popular" },
  { code: "mr-IN", native: "मराठी", name: "Marathi", tag: "Popular" },
  { code: "bn-IN", native: "বাংলা", name: "Bengali", tag: "Popular" },
  { code: "gu-IN", native: "ગુજરાતી", name: "Gujarati", tag: "Popular" },
  { code: "pa-IN", native: "ਪੰਜਾਬੀ", name: "Punjabi", tag: "Popular" },
];

export default function Home() {
  const router = useRouter();
  const [inviteCode, setInviteCode] = useState("");

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = inviteCode.trim().toUpperCase();
    if (clean) {
      router.push(`/join?code=${clean}`);
    }
  };

  return (
    <div className="min-h-screen bg-[#071B20] text-[#F5F7F2] flex flex-col selection:bg-[#00CBA0] selection:text-[#071B20]">
      {/* Top Navbar */}
      <nav className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-5 flex items-center justify-between border-b border-[#1E4D53]/30">
        <div className="flex items-center gap-3">
          <div className="relative w-10 h-10 rounded-xl overflow-hidden shadow-lg shadow-[#00CBA0]/20 border border-[#00CBA0]/40">
            <Image src="/logo.png" alt="Sarvagyan" fill className="object-cover" priority />
          </div>
          <div>
            <span className="text-xl font-bold tracking-tight text-[#F5F7F2] block leading-none">
              Sarvagyan
            </span>
            <span className="text-[10px] tracking-wider uppercase text-[#00CBA0] font-mono">
              Web Companion
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <a
            href="/Sarvagyan.apk"
            download="Sarvagyan.apk"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-[#12363A] hover:bg-[#194449] border border-[#1E4D53] text-[#00CBA0] hover:text-[#00F0A0] transition-all shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>Download APK (58 MB)</span>
          </a>
        </div>
      </nav>

      {/* Hero Section — Widescreen 16:9 Desktop Ratio Grid */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-6 lg:px-12 py-12 lg:py-16 flex flex-col justify-center">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Widescreen Headline & Actions (7 cols) */}
          <div className="lg:col-span-7 flex flex-col items-start text-left">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#12363A]/80 border border-[#1E4D53] text-xs font-semibold tracking-wide text-[#00CBA0] mb-6">
              <span className="w-2 h-2 rounded-full bg-[#00F0A0] animate-ping" />
              Real-Time Neural Speech Translation · Gnani AI
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight text-[#F5F7F2] leading-[1.1]">
              Speak in your language. <br />
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#00CBA0] via-[#00F0A0] to-[#F5B52E]">
                They hear it in theirs.
              </span>
            </h1>

            <p className="mt-6 text-base sm:text-lg text-[#A9BFBA] max-w-xl leading-relaxed">
              No language barriers on calls. Join active calls right from your desktop or mobile browser with live bilingual voice playback and synchronized subtitles across 10 Indian languages.
            </p>

            {/* Quick Join Card & APK CTA */}
            <div className="mt-8 w-full max-w-lg p-6 rounded-2xl glow-card border border-[#1E4D53]/60 bg-[#0B292E]/60 backdrop-blur-md">
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#A9BFBA] mb-3 flex items-center justify-between">
                <span>Join Active Call via Invite Code</span>
                <span className="text-[10px] text-[#00CBA0] font-mono">No install required</span>
              </h2>
              <form onSubmit={handleJoin} className="flex flex-col sm:flex-row gap-2.5">
                <input
                  type="text"
                  maxLength={6}
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  placeholder="Enter 6-letter code"
                  className="flex-1 px-4 py-3 rounded-xl bg-[#071B20] border border-[#1E4D53] text-[#F5F7F2] placeholder-[#A9BFBA]/50 focus:outline-none focus:border-[#00CBA0] uppercase tracking-widest text-center font-mono font-bold text-base"
                />
                <button
                  type="submit"
                  disabled={!inviteCode.trim()}
                  className="px-6 py-3 rounded-xl font-bold glow-button disabled:opacity-40 disabled:cursor-not-allowed text-sm whitespace-nowrap transition-all shadow-lg"
                >
                  Join Call Now →
                </button>
              </form>
            </div>

            <div className="mt-4 flex items-center gap-6 text-xs text-[#A9BFBA]">
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-[#00CBA0]" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                Zero Latency WebSocket Streaming
              </span>
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-[#00CBA0]" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                Chrome / Safari / Edge Supported
              </span>
            </div>
          </div>

          {/* Right Column: 16:9 Widescreen Live Call Interactive Stage Mockup (5 cols) */}
          <div className="lg:col-span-5 w-full">
            <div className="relative rounded-3xl overflow-hidden border border-[#00CBA0]/30 shadow-2xl shadow-[#00CBA0]/15 bg-gradient-to-br from-[#0B292E] to-[#071B20] p-6 flex flex-col aspect-[4/3] sm:aspect-[16/10] justify-between">
              {/* Mockup Header */}
              <div className="flex items-center justify-between border-b border-[#1E4D53]/40 pb-4">
                <div className="flex items-center gap-2.5">
                  <div className="w-3 h-3 rounded-full bg-[#00F0A0] animate-pulse" />
                  <span className="text-xs font-bold text-[#F5F7F2]">Room #IND-782</span>
                </div>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#12363A] text-[#00CBA0] border border-[#1E4D53]">
                  02:14 · Live Call
                </span>
              </div>

              {/* Mockup Participants Cards */}
              <div className="grid grid-cols-2 gap-3 my-auto py-2">
                {/* Speaker 1 (Tamil) */}
                <div className="p-3.5 rounded-2xl bg-[#071B20]/80 border border-[#00CBA0]/40 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#F5F7F2]">Dhanuja</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#FF8A24]/20 text-[#FF8A24] font-semibold">தமிழ்</span>
                  </div>
                  <div className="my-2 h-7 flex items-center justify-center gap-1">
                    <span className="w-1 h-3 bg-[#00CBA0] rounded-full animate-bounce [animation-delay:0ms]" />
                    <span className="w-1 h-6 bg-[#00CBA0] rounded-full animate-bounce [animation-delay:150ms]" />
                    <span className="w-1 h-4 bg-[#00CBA0] rounded-full animate-bounce [animation-delay:300ms]" />
                    <span className="w-1 h-7 bg-[#00CBA0] rounded-full animate-bounce [animation-delay:100ms]" />
                    <span className="w-1 h-3 bg-[#00CBA0] rounded-full animate-bounce [animation-delay:250ms]" />
                  </div>
                  <span className="text-[10px] text-[#A9BFBA] truncate">வணக்கம், எப்படி இருக்கீங்க?</span>
                </div>

                {/* Speaker 2 (Hindi) */}
                <div className="p-3.5 rounded-2xl bg-[#071B20]/80 border border-[#1E4D53] flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#F5F7F2]">Rahul</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#F5B52E]/20 text-[#F5B52E] font-semibold">हिन्दी</span>
                  </div>
                  <div className="my-2 h-7 flex items-center justify-center gap-1">
                    <span className="w-1 h-2 bg-[#F5B52E] rounded-full" />
                    <span className="w-1 h-2 bg-[#F5B52E] rounded-full" />
                    <span className="w-1 h-2 bg-[#F5B52E] rounded-full" />
                  </div>
                  <span className="text-[10px] text-[#00CBA0] truncate">नमस्ते, मैं ठीक हूँ!</span>
                </div>
              </div>

              {/* Live Subtitle Transcript Banner */}
              <div className="p-3 rounded-xl bg-[#071B20]/90 border border-[#1E4D53] text-left">
                <div className="flex items-center justify-between text-[10px] text-[#00CBA0] font-mono mb-1">
                  <span>LIVE BILINGUAL TRANSLATION</span>
                  <span>Gnani Neural Audio</span>
                </div>
                <p className="text-xs text-[#F5F7F2] font-medium leading-snug">
                  &ldquo;வணக்கம், திட்டத்தின் முன்னேற்றம் எப்படி இருக்கிறது?&rdquo;
                </p>
                <p className="text-[11px] text-[#F5B52E] mt-0.5 font-medium leading-snug">
                  → &ldquo;नमस्ते, प्रोजेक्ट का क्या स्टेटस है?&rdquo;
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 10 Supported Indian Languages Grid Showcase */}
        <div className="mt-16 pt-12 border-t border-[#1E4D53]/40">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
            <div>
              <h3 className="text-lg font-bold text-[#F5F7F2]">
                10 Native Indian Languages Supported
              </h3>
              <p className="text-xs text-[#A9BFBA]">
                Full duplex speech recognition, translation, and natural voice playback.
              </p>
            </div>
            <span className="text-xs text-[#00CBA0] font-mono self-start sm:self-auto">
              Gnani STT + MyMemory/Gemini + Gnani TTS
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3.5">
            {LANGUAGES.map((lang) => (
              <div
                key={lang.code}
                className="p-3.5 rounded-2xl bg-[#0B292E]/50 border border-[#1E4D53]/70 hover:border-[#00CBA0]/50 hover:bg-[#12363A]/60 transition-all flex flex-col justify-between"
              >
                <span className="text-lg font-bold text-[#F5F7F2]">{lang.native}</span>
                <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#1E4D53]/40">
                  <span className="text-xs text-[#A9BFBA]">{lang.name}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#071B20] text-[#00CBA0] font-mono">
                    {lang.code.split("-")[0]}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full max-w-7xl mx-auto px-6 lg:px-12 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-[#1E4D53]/30 text-xs text-[#A9BFBA]">
        <p>© 2026 Sarvagyan (सर्वज्ञान) · Primary App on Android · Secondary Companion for Web</p>
        <div className="flex items-center gap-6">
          <Link href="/join" className="hover:text-[#00CBA0] transition-colors">
            Join Call Room
          </Link>
          <a href="/Sarvagyan.apk" download className="hover:text-[#00CBA0] transition-colors">
            Download APK
          </a>
        </div>
      </footer>
    </div>
  );
}
