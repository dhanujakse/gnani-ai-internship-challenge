"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Api, loadSession, type Language, type User } from "@/lib/api";
import { CallEngine, initialCallState, type CallState, type Turn } from "@/lib/callEngine";
import { Avatar, Brand, Icon, LanguagePicker, PrimaryButton, SecondaryButton, StatusChip, TextButton, langLabel } from "./ui";

export interface ActiveCall {
  callId: string;
  code: string;
  mode: "invite" | "joined" | "outgoing" | "answered";
  peerName?: string | null;
  reachable?: boolean;
  /** set from the app socket when a ringing call is declined / missed / busy */
  outcome?: string | null;
}

const OUTCOMES: Record<string, string> = {
  declined: "Declined",
  missed: "No answer",
  no_answer: "No answer",
  busy: "Busy",
  cancelled: "Call cancelled.",
};

export function CallScreen({
  call,
  me,
  language,
  languages,
  onClose,
}: {
  call: ActiveCall;
  me: User;
  language: string;
  languages: Language[];
  onClose: () => void;
}) {
  const [state, setState] = useState<CallState>(initialCallState);
  const [myLang, setMyLang] = useState(language);
  const [langOpen, setLangOpen] = useState(false);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const engine = useRef<CallEngine | null>(null);
  const feedEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const e = new CallEngine(
      call.callId,
      () => loadSession()?.token ?? "",
      language,
      me.id,
      setState,
      () => Api.me().then(() => true).catch(() => false),
    );
    engine.current = e;
    e.start();
    return () => e.cleanup();
    // one engine per call
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [call.callId]);

  // a ringing call that ends before anyone answers (declined, missed, busy)
  useEffect(() => {
    if (call.outcome && engine.current && engine.current.snapshot.status !== "connected") engine.current.hangUp();
  }, [call.outcome]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const turnCount = state.turns.length;
  const lastRev = state.turns.at(-1)?.rev;
  useEffect(() => {
    feedEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turnCount, lastRev]);

  const s = state;
  const peer = s?.peer;
  const peerName = peer?.name ?? call.peerName ?? "Them";
  const ringing = call.mode === "outgoing" && !peer?.connected && s?.status !== "ended";
  const duration = s?.startedAt ? Math.max(0, Math.floor(((s.endedAt ?? now) - s.startedAt) / 1000)) : 0;

  const hangUp = async () => {
    setConfirmEnd(false);
    if (call.mode === "outgoing" && !peer?.connected) await Api.cancel(call.callId).catch(() => undefined);
    engine.current?.hangUp();
  };

  if (!s) return null;

  if (s.status === "ended") {
    return (
      <CallSummary
        reason={call.outcome ? (OUTCOMES[call.outcome] ?? s.endReason) : s.endReason}
        duration={duration}
        turns={s.turns}
        myId={me.id}
        peerName={peerName}
        languages={languages}
        onClose={onClose}
      />
    );
  }

  const status = (() => {
    if (s.status === "reconnecting") return <StatusChip tone="warning" pulsing>Reconnecting…</StatusChip>;
    if (s.status === "connecting") return <StatusChip pulsing>Connecting…</StatusChip>;
    if (ringing) return <StatusChip tone="warning" pulsing>{call.reachable === false ? "Their phone is offline" : "Ringing"}</StatusChip>;
    if (s.status === "waiting") return <StatusChip pulsing>Waiting for them to join</StatusChip>;
    return <StatusChip tone="success">Connected</StatusChip>;
  })();

  const inviteLink = typeof window !== "undefined" ? `${window.location.origin}/join?code=${call.code}` : "";

  return (
    <div className="sg-app-bg flex h-dvh flex-col">
      <header className="border-b border-line/60">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <span className="hidden sm:block">
            <Brand size={30} />
          </span>
          <span className="text-[15px] font-semibold text-ink sm:ml-4">Live translation</span>
          {status}
          <span className="ml-auto font-mono text-[15px] tabular-nums text-sub">{s.startedAt ? fmt(duration) : "--:--"}</span>
        </div>
      </header>

      <main className="mx-auto grid min-h-0 w-full max-w-6xl flex-1 gap-4 px-4 py-4 sm:px-6 lg:grid-cols-[340px_1fr] lg:gap-6 lg:py-6">
        {/* people */}
        <aside className="flex flex-col gap-3 lg:gap-4">
          <PersonTile
            name={peerName}
            avatar={peer?.avatar}
            language={peer ? langLabel(languages, peer.language) : null}
            speaking={s.peerSpeaking}
            note={!peer?.connected ? (ringing ? `Calling ${peerName}…` : "Waiting for someone to join") : peer.muted ? "Muted" : null}
          />
          <PersonTile
            name="You"
            avatar={me.avatar}
            language={langLabel(languages, myLang)}
            speaking={s.meSpeaking}
            note={
              s.error?.startsWith("Microphone needed")
                ? "Microphone needed"
                : !s.micReady
                  ? "Connecting audio…"
                  : s.muted
                    ? "Muted"
                    : s.playing
                      ? "Playing their translated voice"
                      : null
            }
            me
          />
          {(call.mode === "invite" || call.mode === "joined") && s.status === "waiting" && (
            <div className="rounded-lg border border-line bg-card p-5">
              <p className="text-[13px] font-medium text-sub">Invitation code</p>
              <p className="mt-1 font-mono text-[30px] font-bold tracking-[0.25em] text-highlight" aria-label={`Invitation code ${call.code.split("").join(" ")}`}>
                {call.code}
              </p>
              <p className="mt-2 text-[14px] leading-5 text-sub">Share this code. The call starts when they join.</p>
              <div className="mt-4 flex gap-2">
                <CopyButton text={call.code} label="Copy" />
                <SecondaryButton
                  icon="share"
                  onClick={() =>
                    navigator.share
                      ? navigator.share({ title: "Sarvagyan invite", text: `Join my Sarvagyan call with code ${call.code}`, url: inviteLink }).catch(() => undefined)
                      : navigator.clipboard.writeText(inviteLink)
                  }
                >
                  Share
                </SecondaryButton>
              </div>
            </div>
          )}
        </aside>

        {/* subtitles */}
        <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-line bg-bg2" aria-label="Live subtitles">
          <div className="flex items-center justify-between border-b border-line/60 px-5 py-3">
            <span className="text-[15px] font-semibold text-ink">Subtitles</span>
            <span className="text-[13px] text-low">I speak: {langLabel(languages, myLang)}</span>
          </div>
          <div className="min-h-[240px] flex-1 space-y-3 overflow-y-auto p-4 sm:p-5" aria-live="polite">
            {s.turns.length === 0 ? (
              <div className="grid h-full place-items-center text-center">
                <div>
                  <p className="text-[16px] font-semibold text-ink">{peer?.connected ? "Start talking" : "Waiting for them to join"}</p>
                  <p className="mx-auto mt-1 max-w-sm text-[14px] leading-5 text-sub">
                    Speak in full sentences and pause briefly at the end. Use a headset to avoid echo.
                  </p>
                </div>
              </div>
            ) : (
              s.turns.map((t) => <TurnBubble key={t.id} t={t} mine={t.speakerId === me.id} peerName={peerName} languages={languages} onRetry={() => engine.current?.retry(t.id)} />)
            )}
            <div ref={feedEnd} />
          </div>
          {(s.notice || s.error) && (
            <div className={`border-t px-5 py-2.5 text-[14px] ${s.error ? "border-danger/40 bg-danger/10 text-ink" : "border-line/60 text-sub"}`} role="status">
              {s.error ?? s.notice}
            </div>
          )}
          <p className="border-t border-line/60 px-5 py-2 text-[12px] text-low">
            On the web you hear their translated voice and read subtitles. Their original voice is carried in the Android app.
          </p>
        </section>
      </main>

      {/* controls */}
      <footer className="border-t border-line/60">
        <div className="mx-auto flex max-w-6xl items-center justify-center gap-3 px-4 py-4 sm:gap-4">
          <ControlButton
            icon={s.muted ? "micOff" : "mic"}
            label={s.muted ? "Muted" : "Mic on"}
            active={s.muted}
            onClick={() => engine.current?.setMuted(!s.muted)}
          />
          <ControlButton icon="language" label="Change language" onClick={() => setLangOpen(true)} />
          <button
            type="button"
            onClick={() => (peer?.connected ? setConfirmEnd(true) : hangUp())}
            className="flex flex-col items-center gap-1.5"
            aria-label="End call"
          >
            <span className="grid h-14 w-14 place-items-center rounded-full bg-danger text-white transition-colors hover:bg-[#d93355]">
              <Icon name="callEnd" size={26} />
            </span>
            <span className="text-[12px] font-medium text-sub">End call</span>
          </button>
        </div>
      </footer>

      {langOpen && (
        <Dialog title="Switch speaking language" onClose={() => setLangOpen(false)}>
          <p className="mb-4 text-[14px] leading-5 text-sub">Changes what you speak mid-call. Your peer&apos;s audio stays connected.</p>
          <LanguagePicker
            title="Speaking language"
            languages={languages}
            selected={myLang}
            onSelect={(code) => {
              setMyLang(code);
              engine.current?.setLanguage(code);
              setLangOpen(false);
            }}
          />
        </Dialog>
      )}
      {confirmEnd && (
        <Dialog title="End this call?" onClose={() => setConfirmEnd(false)}>
          <div className="mt-2 flex justify-end gap-2">
            <TextButton onClick={() => setConfirmEnd(false)}>Keep talking</TextButton>
            <button type="button" onClick={hangUp} className="rounded-md bg-danger px-4 py-2 text-[15px] font-semibold text-white hover:bg-[#d93355]">
              End call
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}

function PersonTile({ name, avatar, language, speaking, note, me }: { name: string; avatar?: string | null; language: string | null; speaking: boolean; note: string | null; me?: boolean }) {
  return (
    <div className={`flex items-center gap-4 rounded-lg border bg-card p-4 ${speaking ? "border-highlight/70" : "border-line"}`}>
      <Avatar name={name} avatar={avatar} size={52} ring={speaking} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[16px] font-semibold text-ink">{name}</p>
        {language && <p className="truncate text-[14px] text-sub">{language}</p>}
        {note && <p className={`mt-0.5 text-[13px] ${me && note === "Microphone needed" ? "text-[#ff6b81]" : "text-low"}`}>{note}</p>}
      </div>
      {speaking && <Bars />}
    </div>
  );
}

function Bars() {
  return (
    <span className="flex h-6 items-center gap-[3px]" aria-label="Speaking">
      {[0, 120, 240, 90, 200].map((d, i) => (
        <span key={i} className="sg-bar block h-6 w-[3px] rounded-full bg-highlight" style={{ animationDelay: `${d}ms` }} />
      ))}
    </span>
  );
}

function TurnBubble({ t, mine, peerName, languages, onRetry }: { t: Turn; mine: boolean; peerName: string; languages: Language[]; onRetry: () => void }) {
  const who = mine ? `You · ${langLabel(languages, t.sourceLang, false)}` : peerName;
  const listening = t.stage === "listening";
  const working = t.stage === "recognized" || t.stage === "translating";
  // their turns: show what they said in MY language first; mine: what I said, then what they heard
  const main = mine ? t.original : (t.translation ?? t.original);
  const second = mine ? t.translation : t.translation ? t.original : null;
  return (
    <div className={`max-w-[88%] rounded-md border p-3.5 sm:max-w-[80%] ${mine ? "ml-auto border-highlight/25 bg-elevated" : "mr-auto border-line bg-card"}`}>
      <div className="mb-1 flex items-center gap-2 text-[12px] font-medium">
        <span className={mine ? "text-highlight" : "text-gold"}>{who}</span>
        {t.delayMs != null && t.stage !== "failed" && (
          <span className={t.delayMs > 3000 ? "text-warning" : "text-low"}>
            {(t.delayMs / 1000).toFixed(1)} s{t.delayMs > 3000 ? " · translation was slow" : ""}
          </span>
        )}
      </div>
      {listening ? (
        <p className="flex items-center gap-2 text-[15px] text-sub">
          <Bars /> {mine ? "Listening to you…" : `${peerName} is speaking…`}
        </p>
      ) : (
        <>
          <p className="text-[16px] leading-6 text-ink">{main}</p>
          {working && <p className="mt-1 text-[13px] text-sub">Translating…</p>}
          {second && (
            <p className="mt-2 border-t border-white/10 pt-2 text-[14px] leading-5 text-sub">
              <span className="mr-1 text-[12px] font-medium text-low">{mine ? "Translated" : "Original"}</span>
              {second}
            </p>
          )}
          {t.stage === "skipped" && <p className="mt-1 text-[12px] text-low">Subtitles only</p>}
          {t.stage === "failed" && (
            <div className="mt-2 flex items-center gap-2 text-[13px] text-[#ff6b81]">
              <span className="flex-1">{t.error ?? "Translation failed."}</span>
              <TextButton onClick={onRetry}>Retry</TextButton>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ControlButton({ icon, label, onClick, active }: { icon: "mic" | "micOff" | "language"; label: string; onClick: () => void; active?: boolean }) {
  return (
    <button type="button" onClick={onClick} className="flex flex-col items-center gap-1.5" aria-pressed={active}>
      <span className={`grid h-14 w-14 place-items-center rounded-full border transition-colors ${active ? "border-warning/60 bg-warning/15 text-warning" : "border-line bg-card text-ink hover:bg-elevated"}`}>
        <Icon name={icon} size={24} />
      </span>
      <span className="text-[12px] font-medium text-sub">{label}</span>
    </button>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <SecondaryButton
      icon={done ? "check" : "copy"}
      onClick={() => {
        navigator.clipboard.writeText(text).then(() => {
          setDone(true);
          setTimeout(() => setDone(false), 1800);
        });
      }}
    >
      {done ? "Copied" : label}
    </SecondaryButton>
  );
}

export function Dialog({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className="w-full max-w-md rounded-lg border border-line bg-bg2 p-6 shadow-2xl">
        <h2 className="mb-3 text-[20px] font-semibold text-ink">{title}</h2>
        {children}
      </div>
    </div>
  );
}

function CallSummary({
  reason,
  duration,
  turns,
  myId,
  peerName,
  languages,
  onClose,
}: {
  reason: string | null;
  duration: number;
  turns: Turn[];
  myId: string;
  peerName: string;
  languages: Language[];
  onClose: () => void;
}) {
  const said = useMemo(() => turns.filter((t) => t.original && t.stage !== "listening"), [turns]);
  return (
    <div className="sg-app-bg min-h-dvh">
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 py-10 sm:px-6">
      <Brand />
      <h1 className="mt-10 text-[26px] font-semibold text-ink">Call summary</h1>
      {reason && reason !== "Call ended" && <p className="mt-1 text-[15px] text-sub">{reason}</p>}
      <dl className="mt-6 grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-line bg-card p-4">
          <dt className="text-[13px] text-sub">Duration</dt>
          <dd className="mt-1 font-mono text-[22px] text-ink">{fmt(duration)}</dd>
        </div>
        <div className="rounded-lg border border-line bg-card p-4">
          <dt className="text-[13px] text-sub">Translated</dt>
          <dd className="mt-1 text-[22px] text-ink">{said.filter((t) => t.translation).length}</dd>
        </div>
      </dl>

      <h2 className="mb-3 mt-8 text-[16px] font-semibold text-ink">Transcript</h2>
      {said.length === 0 ? (
        <p className="text-[15px] text-sub">Nothing was said in this call.</p>
      ) : (
        <ol className="space-y-3">
          {said.map((t) => (
            <li key={t.id} className="rounded-md border border-line bg-card p-3.5">
              <p className="text-[12px] font-medium text-highlight">{t.speakerId === myId ? `You · ${langLabel(languages, t.sourceLang, false)}` : peerName}</p>
              <p className="mt-1 text-[15px] text-ink">{t.original}</p>
              {t.translation && <p className="mt-1 text-[14px] text-sub">{t.translation}</p>}
            </li>
          ))}
        </ol>
      )}
      <p className="mt-4 text-[13px] text-low">This transcript isn&apos;t saved. Audio was not recorded.</p>
      <PrimaryButton onClick={onClose} className="mt-8 w-full sm:w-auto">
        Back to home
      </PrimaryButton>
    </div>
    </div>
  );
}

function fmt(sec: number) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
