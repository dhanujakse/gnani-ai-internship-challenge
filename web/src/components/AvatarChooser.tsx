"use client";

// The app's ChooseAvatarScreen (ui/screens/AvatarScreens.kt): built-in avatars, "Upload a photo", "Use initials".
// Used right after creating an account (isOnboarding) and from Settings.

import { useRef, useState } from "react";
import { Api, ApiError, type User } from "@/lib/api";
import { Avatar, Brand, ErrorBanner, PrimaryButton, SecondaryButton, Spinner, TextButton } from "./ui";

const BUILT_IN = Array.from({ length: 14 }, (_, i) => `avatar-${String(i + 1).padStart(2, "0")}`);
const MAX_BYTES = 2 * 1024 * 1024;

export function AvatarChooser({ user, onUser, preview = true }: { user: User; onUser: (u: User) => void; preview?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const run = async (work: () => Promise<User>, ok?: string) => {
    if (busy) return;
    setBusy(true);
    setMessage(null);
    try {
      onUser(await work());
      if (ok) setMessage({ ok: true, text: ok });
    } catch (e) {
      setMessage({ ok: false, text: e instanceof ApiError ? e.message : "Could not upload photo." });
    } finally {
      setBusy(false);
    }
  };

  const upload = (f: File | undefined) => {
    if (file.current) file.current.value = "";
    if (!f) return;
    if (f.size > MAX_BYTES) return setMessage({ ok: false, text: "Avatar photo is too large (max 2 MB)." });
    run(() => Api.uploadAvatar(f), "Profile photo updated!");
  };

  return (
    <div>
      {preview && (
        <div className="flex flex-col items-center">
          <div className="relative grid place-items-center">
            <Avatar name={user.display_name} avatar={user.avatar} size={112} ring />
            {busy && (
              <span className="absolute inset-0 grid place-items-center rounded-full bg-bg/60 text-highlight">
                <Spinner size={32} />
              </span>
            )}
          </div>
          <p className="mt-3 text-[18px] font-semibold text-ink">{user.display_name}</p>
          {user.username && <p className="text-[14px] text-highlight">@{user.username}</p>}
        </div>
      )}

      <div className={`flex flex-wrap items-center gap-2 ${preview ? "mt-5 justify-center" : ""}`}>
        <input ref={file} type="file" accept="image/*" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
        <SecondaryButton onClick={() => file.current?.click()} disabled={busy}>
          Upload a photo
        </SecondaryButton>
        {user.avatar && (
          <TextButton onClick={() => run(() => Api.updateMe({ avatar: "" }))} disabled={busy}>
            Use initials
          </TextButton>
        )}
      </div>

      {message && (
        <div className={`mt-3 ${preview ? "text-center" : ""}`}>
          {message.ok ? <p className="text-[13px] text-highlight">{message.text}</p> : <ErrorBanner message={message.text} />}
        </div>
      )}

      <div className="mt-6 grid grid-cols-4 gap-3 sm:grid-cols-7" role="radiogroup" aria-label="Choose your avatar">
        {BUILT_IN.map((id, i) => {
          const on = user.avatar === id;
          return (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={on}
              aria-label={`Avatar ${i + 1}`}
              disabled={busy}
              onClick={() => run(() => Api.updateMe({ avatar: id }))}
              className={`aspect-square overflow-hidden rounded-full ring-offset-2 ring-offset-bg2 transition ${on ? "ring-[3px] ring-highlight" : "ring-1 ring-line hover:ring-2 hover:ring-highlight/60"}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- small local webp thumbnails */}
              <img src={`/avatars/${id}-thumb.webp`} alt="" className="h-full w-full object-cover" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Shown once, right after "Create account" (the app's onboarding avatar step). */
export function AvatarOnboarding({ user, onUser, onDone }: { user: User; onUser: (u: User) => void; onDone: () => void }) {
  return (
    <div className="sg-landing flex min-h-dvh flex-col">
      <header className="border-b border-line/60 bg-bg/40 backdrop-blur-sm">
        <div className="mx-auto flex h-[72px] max-w-6xl items-center justify-between px-4 sm:px-6">
          <Brand />
          <TextButton onClick={onDone}>Skip</TextButton>
        </div>
      </header>
      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <section className="w-full max-w-xl rounded-lg border border-line bg-bg2/95 p-6 backdrop-blur sm:p-8" aria-labelledby="choose-avatar">
          <h1 id="choose-avatar" className="text-center text-[22px] font-semibold text-ink">
            Choose your avatar
          </h1>
          <p className="mb-6 mt-1 text-center text-[15px] text-sub">This is how people see you in calls and contacts.</p>
          <AvatarChooser user={user} onUser={onUser} />
          <PrimaryButton onClick={onDone} className="mt-8 w-full">
            Continue
          </PrimaryButton>
        </section>
      </main>
    </div>
  );
}
