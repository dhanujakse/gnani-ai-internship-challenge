"use client";

// Web versions of the app's shared components (ui/components/Components.kt): PrimaryButton, AppCard, StatusChip,
// LanguagePill, Avatar, EmptyState, ErrorBanner, SectionTitle, and the sign-up LanguagePickerField.

import Image from "next/image";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Api, type Language } from "@/lib/api";

// ---------- icons (Material Icons, as used in the app) ----------

const PATHS = {
  call: "M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z",
  callEnd: "M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85-.18.18-.43.28-.7.28-.28 0-.53-.11-.71-.29L.29 13.08c-.18-.17-.29-.42-.29-.7 0-.28.11-.53.29-.71C3.34 8.78 7.46 7 12 7s8.66 1.78 11.71 4.67c.18.18.29.43.29.71 0 .28-.11.53-.29.71l-2.48 2.48c-.18.18-.43.29-.71.29-.27 0-.52-.11-.7-.28-.79-.74-1.69-1.36-2.67-1.85-.33-.16-.56-.5-.56-.9v-3.1C15.15 9.25 13.6 9 12 9z",
  mic: "M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z",
  micOff: "M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-2.76 0-5.3-2.1-5.3-5.1H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c.91-.13 1.77-.45 2.54-.9L19.73 21 21 19.73 4.27 3z",
  people: "M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z",
  settings: "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z",
  home: "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z",
  help: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z",
  logout: "M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z",
  star: "M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z",
  starBorder: "M22 9.24l-7.19-.62L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.63-7.03L22 9.24zM12 15.4l-3.76 2.27 1-4.28-3.32-2.88 4.38-.38L12 6.1l1.71 4.04 4.38.38-3.32 2.88 1 4.28L12 15.4z",
  language: "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z",
  copy: "M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z",
  share: "M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z",
  download: "M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z",
  personAdd: "M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z",
  history: "M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z",
  dropDown: "M7 10l5 5 5-5z",
  check: "M9 16.17L4.83 12l-1.42 1.42L9 19 21 7l-1.41-1.41z",
  close: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
  arrowForward: "M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z",
  voice: "M9 13c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4zm7.76-9.64l-1.68 1.69c.84 1.18.84 2.71 0 3.89l1.68 1.69c2.02-2.02 2.02-5.07 0-7.27zM20.07 2l-1.63 1.63c2.77 3.02 2.77 7.56 0 10.74L20.07 16c3.9-3.89 3.91-9.95 0-14z",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 20, className = "" }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden="true" className={`shrink-0 ${className}`}>
      <path d={PATHS[name]} />
    </svg>
  );
}

// ---------- brand ----------

/** The original Sarvagyan logo, shown as-is: no circle, frame or crop. */
export function Logo({ size = 36 }: { size?: number }) {
  return <Image src="/logo.png" alt="Sarvagyan" width={size} height={size} priority style={{ width: size, height: size }} />;
}

export function Brand({ size = 34 }: { size?: number }) {
  return (
    <span className="flex items-center gap-2.5">
      <Logo size={size} />
      <span className="text-[19px] font-semibold tracking-tight text-ink">Sarvagyan</span>
    </span>
  );
}

// ---------- building blocks ----------

export function PrimaryButton({
  children,
  onClick,
  disabled,
  loading,
  type = "button",
  icon,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  type?: "button" | "submit";
  icon?: IconName;
  className?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex min-h-[52px] items-center justify-center gap-2 rounded-md bg-accent px-5 text-[15px] font-semibold text-ink transition-colors hover:bg-[#00ad85] disabled:cursor-not-allowed disabled:bg-card/60 disabled:text-sub/40 ${className}`}
    >
      {loading ? <Spinner /> : icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
}

export function SecondaryButton({ children, onClick, disabled, icon, className = "" }: { children: ReactNode; onClick?: () => void; disabled?: boolean; icon?: IconName; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md border border-line px-4 text-[15px] font-semibold text-highlight transition-colors hover:bg-elevated disabled:opacity-40 ${className}`}
    >
      {icon && <Icon name={icon} size={18} />}
      {children}
    </button>
  );
}

export function TextButton({ children, onClick, disabled, danger }: { children: ReactNode; onClick?: () => void; disabled?: boolean; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-sm px-3 py-2 text-[15px] font-semibold transition-colors disabled:opacity-40 ${danger ? "text-danger hover:bg-danger/10" : "text-highlight hover:bg-highlight/10"}`}
    >
      {children}
    </button>
  );
}

export function IconButton({ icon, label, onClick, active, className = "" }: { icon: IconName; label: string; onClick?: () => void; active?: boolean; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`grid h-10 w-10 place-items-center rounded-full transition-colors hover:bg-elevated ${active ? "text-gold" : "text-sub hover:text-ink"} ${className}`}
    >
      <Icon name={icon} />
    </button>
  );
}

export function Spinner({ size = 20 }: { size?: number }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className="inline-block animate-spin rounded-full border-2 border-current border-t-transparent"
      style={{ width: size, height: size }}
    />
  );
}

export function AppCard({ children, className = "", onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  const cls = `rounded-lg border border-line bg-card p-5 ${onClick ? "cursor-pointer text-left transition-colors hover:bg-elevated" : ""} ${className}`;
  return onClick ? (
    <button type="button" onClick={onClick} className={`block w-full ${cls}`}>
      {children}
    </button>
  ) : (
    <div className={cls}>{children}</div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="mb-3 mt-8 text-[16px] font-semibold text-ink first:mt-0">{children}</h3>;
}

type Tone = "success" | "error" | "warning" | "muted";
const TONES: Record<Tone, string> = {
  success: "text-highlight bg-highlight/12 border-highlight/30",
  error: "text-[#ff6b81] bg-danger/15 border-danger/40",
  warning: "text-warning bg-warning/12 border-warning/30",
  muted: "text-sub bg-white/5 border-line",
};

export function StatusChip({ children, tone = "muted", pulsing }: { children: ReactNode; tone?: Tone; pulsing?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[12px] font-medium tracking-[0.3px] ${TONES[tone]}`}>
      <span className={`h-1.5 w-1.5 rounded-full bg-current ${pulsing ? "animate-pulse" : ""}`} />
      {children}
    </span>
  );
}

export function LanguagePill({ children, highlighted }: { children: ReactNode; highlighted?: boolean }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-[13px] font-medium ${highlighted ? "border-highlight/60 bg-highlight/10 text-ink" : "border-line text-sub"}`}>
      {children}
    </span>
  );
}

export function EmptyState({ icon, title, body }: { icon: IconName; title: string; body: string }) {
  return (
    <div className="flex flex-col items-center px-4 py-8 text-center">
      <span className="mb-3 grid h-12 w-12 place-items-center rounded-full bg-bg2 text-sub">
        <Icon name={icon} size={24} />
      </span>
      <p className="text-[15px] font-semibold text-ink">{title}</p>
      <p className="mt-1 max-w-xs text-[14px] leading-5 text-sub">{body}</p>
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center gap-3 rounded-md border border-danger/50 bg-danger/15 px-4 py-3 text-[14px] text-ink">
      <span className="flex-1">{message}</span>
      {onRetry && <TextButton onClick={onRetry}>Retry</TextButton>}
    </div>
  );
}

// ---------- form fields (OutlinedTextField look) ----------

export function TextField({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  prefix,
  supporting,
  error,
  supportingTone,
  autoComplete,
  inputMode,
  maxLength,
  className = "",
  mono,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  prefix?: string;
  supporting?: ReactNode;
  error?: boolean;
  supportingTone?: "ok" | "error" | "muted";
  autoComplete?: string;
  inputMode?: "text" | "email" | "tel" | "search";
  maxLength?: number;
  className?: string;
  mono?: boolean;
}) {
  const tone = supportingTone ?? (error ? "error" : "muted");
  return (
    <label className={`block ${className}`}>
      {label && <span className="mb-1.5 block text-[13px] font-medium text-sub">{label}</span>}
      <span
        className={`flex items-center rounded-md border bg-bg2 px-4 transition-colors focus-within:border-highlight ${error ? "border-danger" : "border-line"}`}
      >
        {prefix && <span className="mr-0.5 text-[16px] text-sub">{prefix}</span>}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          inputMode={inputMode}
          maxLength={maxLength}
          className={`min-h-[52px] w-full bg-transparent text-[16px] text-ink outline-none placeholder:text-low ${mono ? "font-mono tracking-[0.3em] uppercase" : ""}`}
        />
      </span>
      {supporting && (
        <span className={`mt-1.5 block px-1 text-[12px] ${tone === "ok" ? "text-highlight" : tone === "error" ? "text-[#ff6b81]" : "text-sub"}`}>{supporting}</span>
      )}
    </label>
  );
}

/** The app's LanguagePickerField: "Which language do you speak?", no pre-selected option. */
export function LanguagePicker({
  title = "Which language do you speak?",
  languages,
  selected,
  onSelect,
}: {
  title?: string;
  languages: Language[];
  selected: string | null;
  onSelect: (code: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = languages.find((l) => l.code === selected);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <div ref={ref} className="relative">
      {title && <span className="mb-1.5 block text-[14px] font-semibold text-ink">{title}</span>}
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={`flex min-h-[52px] w-full items-center gap-3 rounded-md border bg-card px-4 text-left transition-colors hover:bg-elevated ${selected ? "border-highlight border-[1.5px]" : "border-line"}`}
      >
        <Icon name="language" className={selected ? "text-highlight" : "text-sub"} />
        <span className={`flex-1 text-[16px] ${selected ? "text-ink" : "text-sub"}`}>{current ? `${current.native} · ${current.name}` : "Select your language…"}</span>
        <Icon name="dropDown" className="text-sub" />
      </button>
      {open && (
        <ul role="listbox" className="absolute z-30 mt-1 max-h-72 w-full overflow-auto rounded-md border border-line bg-elevated py-1 shadow-2xl shadow-black/40">
          {languages.map((l) => (
            <li key={l.code}>
              <button
                type="button"
                role="option"
                aria-selected={l.code === selected}
                onClick={() => {
                  onSelect(l.code);
                  setOpen(false);
                }}
                className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-[15px] text-ink hover:bg-card"
              >
                <span className="flex-1">
                  {l.native} · {l.name}
                </span>
                {l.code === selected && <Icon name="check" size={18} className="text-highlight" />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------- avatar (built-in avatars from the app, or an uploaded photo) ----------

const blobCache = new Map<string, string>();

export function Avatar({ name, avatar, size = 40, ring }: { name: string; avatar?: string | null; size?: number; ring?: boolean }) {
  const [loaded, setLoaded] = useState<{ key: string; url: string } | null>(null);
  const big = size > 64; // large previews use the 512 px image, lists the 128 px thumbnail
  const key = avatar ? `${avatar}|${big ? "main" : "thumb"}` : "";
  // uploaded photos need the sign-in token, so they are fetched once and kept as blob: URLs
  useEffect(() => {
    if (!avatar?.startsWith("custom:") || blobCache.has(key)) return;
    let alive = true;
    Api.avatarBlob(avatar.slice(7), !big)
      .then((b) => {
        const url = URL.createObjectURL(b);
        blobCache.set(key, url);
        if (alive) setLoaded({ key, url });
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [avatar, big, key]);
  const src = avatar?.startsWith("avatar-")
    ? `/avatars/${avatar}${big ? "" : "-thumb"}.webp`
    : avatar?.startsWith("custom:")
      ? (blobCache.get(key) ?? (loaded?.key === key ? loaded.url : null))
      : null;
  const initial = (name.trim()[0] || "?").toUpperCase();
  return (
    <span
      className={`grid shrink-0 place-items-center overflow-hidden rounded-full bg-elevated font-semibold text-highlight ${ring ? "ring-2 ring-highlight/60" : ""}`}
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- blob: URLs and local webp thumbnails
        <img src={src} alt="" width={size} height={size} className="h-full w-full object-cover" />
      ) : (
        initial
      )}
    </span>
  );
}

export function langLabel(languages: Language[], code: string | null | undefined, native = true) {
  const l = languages.find((x) => x.code === code);
  if (!l) return code ?? "";
  return native ? `${l.native} · ${l.name}` : l.name;
}
