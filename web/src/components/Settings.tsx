"use client";

import { useState } from "react";
import { Api, ApiError, type Language, type User } from "@/lib/api";
import { phoneHash } from "@/lib/phone";
import { AvatarChooser } from "./AvatarChooser";
import { AppCard, Avatar, ErrorBanner, Icon, LanguagePicker, PrimaryButton, SecondaryButton, SectionTitle, StatusChip, TextField } from "./ui";


/** The app's Settings, the parts that apply on the web: profile, language, diagnostics, sign out. */
export function Settings({ user, languages, onUser, onSignOut }: { user: User; languages: Language[]; onUser: (u: User) => void; onSignOut: () => void }) {
  return (
    <div className="max-w-3xl">
      <h1 className="mb-6 text-[26px] font-semibold text-ink">Settings</h1>
      <Profile user={user} onUser={onUser} />
      <SectionTitle>Language and voice</SectionTitle>
      <AppCard>
        <LanguagePicker
          title="I speak"
          languages={languages}
          selected={user.language}
          onSelect={async (code) => {
            try {
              onUser(await Api.updateMe({ language: code }));
            } catch {
              /* the picker keeps the old value */
            }
          }}
        />
        <p className="mt-2 text-[13px] text-low">Applies to calls you start or join next.</p>
      </AppCard>
      <Diagnostics />
      <SectionTitle>Account</SectionTitle>
      <AppCard>
        <p className="text-[14px] text-sub">Signed in as {user.email ?? user.display_name}</p>
        <button type="button" onClick={onSignOut} className="mt-3 inline-flex items-center gap-2 rounded-sm py-1 text-[15px] font-semibold text-[#ff6b81] hover:underline">
          <Icon name="logout" size={18} /> Sign out
        </button>
      </AppCard>
      <p className="mt-8 text-[12px] text-low">Sarvagyan 1.0.0 · Web</p>
    </div>
  );
}

function Profile({ user, onUser }: { user: User; onUser: (u: User) => void }) {
  const [name, setName] = useState(user.display_name);
  const [nameMsg, setNameMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [phone, setPhone] = useState("");
  const [phoneMsg, setPhoneMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pickAvatar, setPickAvatar] = useState(false);

  const saveName = async () => {
    const n = name.trim();
    if (!n) return setNameMsg({ ok: false, text: "Name cannot be empty." });
    if (n.length > 60) return setNameMsg({ ok: false, text: "Name must be 60 characters or less." });
    try {
      onUser(await Api.updateMe({ display_name: n }));
      setNameMsg({ ok: true, text: "Display name updated!" });
    } catch (e) {
      setNameMsg({ ok: false, text: e instanceof ApiError ? e.message : "Couldn't save your name." });
    }
  };

  const savePhone = async () => {
    const hash = await phoneHash(phone);
    if (!hash) return setPhoneMsg({ ok: false, text: "Enter a valid phone number." });
    try {
      onUser(await Api.updateMe({ phone_hash: hash }));
      setPhone("");
      setPhoneMsg({ ok: true, text: "Phone number saved for contact discovery!" });
    } catch (e) {
      setPhoneMsg({ ok: false, text: e instanceof ApiError ? e.message : "Couldn't save your number." });
    }
  };

  return (
    <>
      <SectionTitle>Profile and username</SectionTitle>
      <AppCard>
        <div className="flex flex-wrap items-center gap-4">
          <Avatar name={user.display_name} avatar={user.avatar} size={72} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[20px] font-semibold text-ink">{user.display_name}</p>
            {user.username && <p className="text-[14px] text-highlight">@{user.username}</p>}
            {user.is_demo && (
              <div className="mt-1">
                <StatusChip tone="warning">Guest account</StatusChip>
              </div>
            )}
          </div>
          <SecondaryButton onClick={() => setPickAvatar((v) => !v)}>{pickAvatar ? "Done" : "Change avatar"}</SecondaryButton>
        </div>

        {pickAvatar && (
          <div className="mt-5 border-t border-line/60 pt-5">
            <p className="mb-3 text-[15px] font-semibold text-ink">Choose your avatar</p>
            <AvatarChooser user={user} onUser={onUser} preview={false} />
          </div>
        )}

        <div className="mt-6 grid gap-4 border-t border-line/60 pt-5 sm:grid-cols-[1fr_auto] sm:items-start">
          <TextField label="Display name" value={name} onChange={setName} maxLength={60} supporting={nameMsg?.text} supportingTone={nameMsg ? (nameMsg.ok ? "ok" : "error") : "muted"} />
          <SecondaryButton onClick={saveName} disabled={name.trim() === user.display_name} className="sm:mt-[26px]">
            Save name
          </SecondaryButton>
          <TextField
            label="Phone number"
            placeholder="Type your number"
            type="tel"
            inputMode="tel"
            value={phone}
            onChange={(v) => setPhone(v.replace(/[^0-9+ -]/g, "").slice(0, 20))}
            supporting={phoneMsg?.text ?? "Used only to help your contacts find you. Stored as a secure hash."}
            supportingTone={phoneMsg ? (phoneMsg.ok ? "ok" : "error") : "muted"}
          />
          <SecondaryButton onClick={savePhone} disabled={!phone.trim()} className="sm:mt-[26px]">
            Save
          </SecondaryButton>
        </div>
        {user.email && <p className="mt-4 text-[13px] text-low">Email: {user.email}</p>}
      </AppCard>
    </>
  );
}

function Diagnostics() {
  const [busy, setBusy] = useState(false);
  const [diag, setDiag] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setDiag(await Api.diagnostics());
    } catch (e) {
      setDiag(null);
      setError(e instanceof ApiError ? e.message : "Can't reach the server.");
    } finally {
      setBusy(false);
    }
  };
  const part = (k: string) => (diag?.[k] as { ok?: boolean; ms?: number; error?: string } | undefined) ?? undefined;
  const line = (label: string, ok: boolean | undefined, detail: string) => (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-[15px] text-ink">{label}</span>
      <StatusChip tone={ok ? "success" : "error"}>{detail}</StatusChip>
    </div>
  );
  const stt = part("speech_recognition");
  const tr = part("translation");
  return (
    <>
      <SectionTitle>Connection and diagnostics</SectionTitle>
      <AppCard>
        <PrimaryButton onClick={run} loading={busy} className="!min-h-[44px]">
          Run diagnostics
        </PrimaryButton>
        {error && (
          <div className="mt-4">
            <ErrorBanner message={error} />
          </div>
        )}
        {diag && (
          <div className="mt-4 divide-y divide-line/50">
            {line("Server", true, "OK")}
            {line("Speech API key", Boolean(diag.gnani_key_configured), diag.gnani_key_configured ? "Configured" : "Missing")}
            {line("Speech recognition", stt?.ok, stt?.ok && stt.ms != null ? `OK · ${stt.ms} ms` : (stt?.error ?? "Failed"))}
            {line("Translation", tr?.ok, tr?.ok && tr.ms != null ? `OK · ${tr.ms} ms` : (tr?.error ?? "Failed"))}
            {line("TURN relay", Boolean(diag.turn_configured), diag.turn_configured ? "Configured" : "Not set (STUN only)")}
          </div>
        )}
      </AppCard>
    </>
  );
}

const HELP: [string, string][] = [
  [
    "How it works",
    "When you speak, Sarvagyan sends your voice to its server, which recognises what you said, translates it and speaks it in the other person's language. They hear the translation and see subtitles; you see what they heard. Their replies come back the same way.",
  ],
  [
    "How fast is it?",
    "Usually 2–5 seconds after you finish a sentence: speech recognition waits for a short pause, then translation and the voice take about a second each. Each subtitle shows the delay, and slow translations are marked.",
  ],
  [
    "Tips for good results",
    "Speak in full sentences and pause briefly at the end. Use a headset or keep the speaker away from the microphone to avoid echo. If translations sound wrong, check that both people picked the right language.",
  ],
  [
    "Privacy",
    "Sarvagyan does not record calls. Speech is processed only to produce the translation. On the web, the call transcript is shown during the call and is not saved.",
  ],
  [
    "Troubleshooting",
    "Can't reach the server: check your internet, then run diagnostics in Settings. No sound: allow the microphone for this site in your browser, and check your speaker or headset.",
  ],
  [
    "Limitations",
    "Calls are between two people inside Sarvagyan. On the web you hear the translated voice and read subtitles; the other person's original voice is carried in the Android app.",
  ],
];

export function Help() {
  return (
    <div className="max-w-3xl">
      <h1 className="mb-6 text-[26px] font-semibold text-ink">Help &amp; Manual</h1>
      {HELP.map(([title, body]) => (
        <section key={title} className="mt-8 first:mt-0">
          <SectionTitle>{title}</SectionTitle>
          <p className="text-[16px] leading-7 text-sub">{body}</p>
        </section>
      ))}
    </div>
  );
}
