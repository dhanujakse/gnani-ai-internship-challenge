"use client";

import { useEffect, useState } from "react";
import { Api, ApiError, type Language, type Session } from "@/lib/api";
import { phoneHash } from "@/lib/phone";
import { Brand, ErrorBanner, Icon, LanguagePicker, Logo, PrimaryButton, TextField, type IconName } from "./ui";

const STEPS: { icon: IconName; title: string; body: string }[] = [
  { icon: "language", title: "Choose your language", body: "Pick the language you speak. Tamil and English first, plus 8 more Indian languages." },
  { icon: "call", title: "Start a call", body: "Share an invitation code, or call someone in your contacts directly." },
  { icon: "voice", title: "Just talk", body: "They hear you in their language and read live subtitles. You hear their reply in yours." },
];

export function Landing({ languages, pendingCode, onSignedIn }: { languages: Language[]; pendingCode: string; onSignedIn: (s: Session, isNew: boolean) => void }) {
  return (
    <div className="sg-landing flex min-h-screen flex-col">
      <header className="border-b border-line/60 bg-bg/40 backdrop-blur-sm">
        <div className="mx-auto flex h-[72px] max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Brand />
          <a
            href="/Sarvagyan.apk"
            download
            aria-label="Download the Android app (APK) for the best experience"
            className="group inline-flex items-center gap-3 rounded-full bg-gradient-to-r from-accent to-highlight py-1.5 pl-1.5 pr-4 text-ink shadow-[0_6px_24px_-6px_rgba(0,203,160,0.55)] ring-1 ring-highlight/40 transition hover:-translate-y-px hover:shadow-[0_10px_30px_-6px_rgba(0,203,160,0.7)] sm:pr-5"
          >
            <span className="grid h-9 w-9 place-items-center rounded-full bg-bg/25">
              <Icon name="download" size={20} />
            </span>
            <span className="text-left leading-tight">
              <span className="block text-[14px] font-bold">Download APK</span>
              <span className="hidden text-[11px] font-medium text-ink/85 sm:block">Android app · best experience</span>
            </span>
          </a>
        </div>
      </header>

      {/* phones: intro, then the form, then the details; desktop: intro + details on the left, form on the right */}
      <main className="mx-auto grid w-full max-w-6xl flex-1 content-center gap-x-16 gap-y-10 px-4 py-10 sm:px-6 lg:grid-cols-[1fr_440px] lg:py-16">
        <section className="lg:col-start-1 lg:row-start-1 lg:self-end">
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-highlight">Every Language. One Connection.</p>
          <h1 className="mt-4 text-[38px] font-bold leading-[1.1] tracking-[-0.5px] text-ink sm:text-[50px]">
            Speak in your language.
            <br />
            <span className="text-highlight">They understand instantly.</span>
          </h1>
          <p className="mt-5 max-w-xl text-[17px] leading-7 text-sub">
            Sarvagyan is voice calling for people who don&apos;t share a language. You speak yours, they hear theirs, and live subtitles
            keep both of you on the same page.
          </p>
        </section>

        <div className="lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:self-center">
          <AuthCard languages={languages} pendingCode={pendingCode} onSignedIn={onSignedIn} />
        </div>

        <section className="lg:col-start-1 lg:row-start-2 lg:self-start" aria-label="How it works">
          <ol className="grid max-w-xl gap-5">
            {STEPS.map((s, i) => (
              <li key={s.title} className="flex gap-4">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-elevated text-highlight">
                  <Icon name={s.icon} size={22} />
                </span>
                <span>
                  <span className="block text-[16px] font-semibold text-ink">
                    {i + 1}. {s.title}
                  </span>
                  <span className="mt-0.5 block text-[15px] leading-6 text-sub">{s.body}</span>
                </span>
              </li>
            ))}
          </ol>

          <div className="mt-10 flex max-w-xl flex-wrap gap-2" aria-label="Supported languages">
            {languages.map((l) => (
              <span key={l.code} title={l.name} className="rounded-full border border-line px-3 py-1 text-[14px] text-sub">
                {l.native}
              </span>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-line/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-5 text-[13px] text-low sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <span>© 2026 Sarvagyan</span>
          <span>Calls are never recorded.</span>
        </div>
      </footer>
    </div>
  );
}

/** The app's AuthScreen: same tabs, fields, labels, placeholders and validation. */
function AuthCard({ languages, pendingCode, onSignedIn }: { languages: Language[]; pendingCode: string; onSignedIn: (s: Session, isNew: boolean) => void }) {
  const [tab, setTab] = useState<0 | 1>(0); // 0 sign in, 1 create account
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [remote, setRemote] = useState<{ name: string; available: boolean; text: string | null } | null>(null);
  const [language, setLanguage] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // live username check, as in the app: local rules first, then the server after 400 ms
  const u = username.trim().replace(/^@/, "");
  const localError = !u ? null : u.length < 3 ? "At least 3 characters needed" : !/^[\p{L}\p{N}_]+$/u.test(u) ? "Letters, numbers, and underscores only" : null;
  const answered = remote?.name === u;
  const checking = !!u && !localError && !answered;
  const usernameAvailable = !localError && answered && remote.available;
  const usernameStatus = !u ? null : (localError ?? (answered ? remote.text : null));

  useEffect(() => {
    if (!u || localError) return;
    let alive = true;
    const t = setTimeout(async () => {
      try {
        const r = await Api.checkUsername(u);
        if (alive)
          setRemote({ name: u, available: r.available, text: r.available ? "✓ Username is available" : (r.reason ?? "This username is already taken. Please choose another username.") });
      } catch {
        if (alive) setRemote({ name: u, available: false, text: null });
      }
    }, 400);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [u, localError]);

  const canSubmit =
    tab === 0
      ? email.includes("@") && password.length >= 1
      : email.includes("@") && password.length >= 8 && name.trim() !== "" && usernameAvailable && !checking && language !== null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (tab === 0) {
        onSignedIn(await Api.login(email.trim(), password), false);
      } else {
        const hash = phone.trim() ? await phoneHash(phone) : null;
        const s = await Api.register({
          email: email.trim(),
          password,
          name: name.trim() || email.split("@")[0],
          username: username.trim().replace(/^@/, ""),
          language: language!,
          phoneHash: hash,
        });
        onSignedIn(s, true);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const usernameTone = checking ? "muted" : usernameStatus ? (usernameAvailable ? "ok" : "error") : "muted";

  return (
    <section className="w-full rounded-lg border border-line bg-bg2/95 p-6 shadow-2xl shadow-black/30 backdrop-blur sm:p-8" aria-label="Sign in or create an account">
      <Logo size={56} />
      <h2 className="mt-4 text-[26px] font-semibold text-ink">Welcome to Sarvagyan</h2>
      <p className="mt-1 text-[15px] text-sub">{pendingCode ? `Sign in to join the call ${pendingCode}.` : "Sign in to start translated calls."}</p>

      <div role="tablist" className="mt-6 grid grid-cols-2 overflow-hidden rounded-full border border-line">
        {(["Sign in", "Create account"] as const).map((label, i) => (
          <button
            key={label}
            role="tab"
            type="button"
            aria-selected={tab === i}
            onClick={() => {
              setTab(i as 0 | 1);
              setError(null);
            }}
            className={`flex h-10 items-center justify-center gap-1.5 text-[14px] font-medium transition-colors ${i === 1 ? "border-l border-line" : ""} ${
              tab === i ? "bg-elevated text-ink" : "text-sub hover:text-ink"
            }`}
          >
            {tab === i && <Icon name="check" size={16} className="text-highlight" />}
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="mt-5 space-y-3" noValidate>
        {tab === 1 && (
          <>
            <TextField label="Your name" value={name} onChange={setName} autoComplete="name" maxLength={60} />
            <TextField
              label="Unique username"
              prefix="@"
              value={username}
              onChange={(v) => setUsername(v.trim().toLowerCase())}
              autoComplete="username"
              maxLength={30}
              error={usernameTone === "error"}
              supportingTone={usernameTone}
              supporting={checking ? "Checking availability..." : (usernameStatus ?? "3-30 letters, numbers, or underscores")}
            />
            <div className="pt-1">
              <LanguagePicker languages={languages} selected={language} onSelect={setLanguage} />
            </div>
            <TextField
              label="Phone number"
              placeholder="Type your number"
              value={phone}
              onChange={(v) => setPhone(v.replace(/[^0-9+ -]/g, "").slice(0, 20))}
              type="tel"
              inputMode="tel"
              autoComplete="tel"
            />
          </>
        )}
        <TextField label="Email" type="email" inputMode="email" value={email} onChange={(v) => setEmail(v.trim())} autoComplete="email" />
        <TextField
          label={tab === 1 ? "Password (8+ characters)" : "Password"}
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete={tab === 1 ? "new-password" : "current-password"}
        />
        {error && (
          <div className="pt-1">
            <ErrorBanner message={error} />
          </div>
        )}
        <PrimaryButton type="submit" disabled={!canSubmit} loading={busy} className="!mt-5 w-full">
          {tab === 0 ? "Sign in" : "Create account"}
        </PrimaryButton>
      </form>
    </section>
  );
}
