"use client";

import { useCallback, useEffect, useState } from "react";
import { Api, ApiError, normaliseCode, type CallRecord, type Contact, type Language, type User } from "@/lib/api";
import { AppCard, Avatar, EmptyState, ErrorBanner, Icon, IconButton, LanguagePill, LanguagePicker, SectionTitle, Spinner, TextField, langLabel } from "./ui";
import { Dialog } from "./CallScreen";

/** The app's HomeScreen: Start a call, Join with an invitation code, I speak, Contacts, favourites, recent calls. */
export function Home({
  user,
  languages,
  pendingCode,
  busy,
  onStartCall,
  onJoin,
  onCallPerson,
  onLanguage,
  onContacts,
}: {
  user: User;
  languages: Language[];
  pendingCode: string;
  busy: boolean;
  onStartCall: () => void;
  onJoin: (code: string) => void;
  onCallPerson: (id: string, name: string) => void;
  onLanguage: (code: string) => Promise<void>;
  onContacts: () => void;
}) {
  const [code, setCode] = useState(pendingCode);
  const [history, setHistory] = useState<CallRecord[] | null>(null);
  const [favourites, setFavourites] = useState<Contact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [langOpen, setLangOpen] = useState(false);

  const [reloads, setReloads] = useState(0);
  const load = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    Promise.all([Api.history(), Api.favourites()])
      .then(([h, f]) => {
        if (!alive) return;
        setHistory(h.calls);
        setFavourites(f.contacts);
        setError(null);
      })
      .catch((e) => {
        if (!alive) return;
        setHistory((prev) => prev ?? []);
        setError(e instanceof ApiError ? e.message : "Couldn't load your calls.");
      });
    return () => {
      alive = false;
    };
  }, [reloads]);

  const star = async (id: string, on: boolean) => {
    await Api.setFavourite(id, on).catch(() => undefined);
    load();
  };

  return (
    <div>
      <div className="mb-6 flex items-center gap-3 lg:hidden">
        <Avatar name={user.display_name} avatar={user.avatar} size={44} />
        <div className="min-w-0">
          <p className="truncate text-[20px] font-semibold text-ink">{user.display_name}</p>
          {user.username && <p className="truncate text-[13px] text-highlight">@{user.username}</p>}
        </div>
      </div>
      <h1 className="mb-6 hidden text-[26px] font-semibold text-ink lg:block">Home</h1>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* the most prominent action */}
        <button
          type="button"
          onClick={onStartCall}
          disabled={busy}
          className="flex min-h-[112px] items-center gap-4 rounded-lg bg-gradient-to-r from-accent to-highlight p-5 text-left text-ink transition-opacity hover:opacity-95 disabled:opacity-70 lg:col-span-2"
        >
          {busy ? <Spinner size={32} /> : <Icon name="call" size={36} />}
          <span>
            <span className="block text-[22px] font-bold">Start a call</span>
            <span className="block text-[15px] text-ink/85">Get an invitation code to share</span>
          </span>
        </button>

        <AppCard>
          <p className="text-[16px] font-semibold text-ink">Join with an invitation code</p>
          <form
            className="mt-3 flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (code.length === 6) onJoin(code);
            }}
          >
            <TextField value={code} onChange={(v) => setCode(normaliseCode(v))} placeholder="ABC234" maxLength={6} mono className="flex-1" />
            <button type="submit" disabled={code.length !== 6 || busy} className="rounded-sm px-4 py-3 text-[15px] font-semibold text-highlight hover:bg-highlight/10 disabled:opacity-40">
              Join
            </button>
          </form>
        </AppCard>

        <AppCard onClick={() => setLangOpen(true)}>
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <p className="text-[16px] font-semibold text-ink">I speak</p>
              <div className="mt-2">
                <LanguagePill highlighted>{langLabel(languages, user.language)}</LanguagePill>
              </div>
            </div>
            <span className="text-[15px] font-semibold text-accent">Change</span>
          </div>
        </AppCard>

        <AppCard onClick={onContacts} className="lg:col-span-2">
          <div className="flex items-center gap-3">
            <Icon name="people" size={28} className="text-highlight" />
            <div>
              <p className="text-[16px] font-semibold text-ink">Contacts</p>
              <p className="text-[14px] text-sub">Call people directly: their phone rings</p>
            </div>
          </div>
        </AppCard>
      </div>

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} onRetry={load} />
        </div>
      )}

      <div className="mt-8 grid gap-x-8 gap-y-2 lg:grid-cols-2">
        <section>
          <SectionTitle>Favourite contacts</SectionTitle>
          {favourites.length === 0 ? (
            <EmptyState icon="starBorder" title="No favourites yet" body="Star someone in Recent calls. Only people you have actually called can be favourites." />
          ) : (
            <ul className="divide-y divide-line/50">
              {favourites.map((f) => (
                <li key={f.id} className="flex items-center gap-3 py-2.5">
                  <Avatar name={f.name} avatar={f.avatar} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[16px] font-semibold text-ink">{f.name}</p>
                    <p className="text-[14px] text-sub">
                      {langLabel(languages, f.language, false)}
                      {f.is_demo ? " · demo account" : ""}
                    </p>
                  </div>
                  <IconButton icon="star" label="Remove favourite" active onClick={() => star(f.id, false)} />
                  <IconButton icon="call" label={`Call ${f.name}`} onClick={() => onCallPerson(f.id, f.name)} className="text-highlight" />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <SectionTitle>Recent calls</SectionTitle>
          {history === null ? (
            <div className="flex items-center gap-3 py-6 text-[15px] text-sub">
              <Spinner /> Loading your calls…
            </div>
          ) : history.length === 0 ? (
            <EmptyState icon="history" title="No calls yet" body="Your translated calls will appear here." />
          ) : (
            <ul className="divide-y divide-line/50">
              {history.slice(0, 15).map((h) => (
                <HistoryRow key={h.call_id} h={h} languages={languages} onStar={(on) => h.peer && star(h.peer.id, on)} onCall={() => h.peer && onCallPerson(h.peer.id, h.peer.name ?? "")} />
              ))}
            </ul>
          )}
        </section>
      </div>

      {langOpen && (
        <Dialog title="I speak" onClose={() => setLangOpen(false)}>
          <p className="mb-4 text-[14px] text-sub">Applies to calls you start or join next.</p>
          <LanguagePicker
            title=""
            languages={languages}
            selected={user.language}
            onSelect={async (c) => {
              setLangOpen(false);
              await onLanguage(c);
            }}
          />
        </Dialog>
      )}
    </div>
  );
}

function HistoryRow({ h, languages, onStar, onCall }: { h: CallRecord; languages: Language[]; onStar: (on: boolean) => void; onCall: () => void }) {
  const peer = h.peer;
  const missed = h.status === "missed" || ["missed", "no_answer", "cancelled"].includes(h.outcome ?? "");
  const outcome = missed ? "Missed call" : h.outcome === "declined" ? "Declined" : h.outcome === "busy" ? "Busy" : null;
  const meta = [
    outcome,
    missed && h.has_voicemail ? "Voicemail" : null,
    new Date(h.created_at * 1000).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }),
    h.duration_s != null ? formatDuration(h.duration_s) : null,
    h.utterances > 0 ? `${h.utterances} translated` : null,
    peer?.is_demo ? "demo" : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <li className="flex items-center gap-3 py-2.5">
      <Avatar name={peer?.name ?? "Nobody"} avatar={peer?.avatar} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-[16px] font-semibold text-ink">{peer?.name ?? "Nobody joined"}</p>
        <p className={`truncate text-[14px] ${missed ? "text-[#ff6b81]" : "text-sub"}`}>{meta}</p>
        {peer && <p className="sr-only">{langLabel(languages, peer.language, false)}</p>}
      </div>
      {peer && (
        <>
          <IconButton icon={peer.favourite ? "star" : "starBorder"} label={peer.favourite ? "Remove favourite" : "Add favourite"} active={peer.favourite} onClick={() => onStar(!peer.favourite)} />
          <IconButton icon="call" label={`Call ${peer.name ?? ""}`} onClick={onCall} className="text-highlight" />
        </>
      )}
    </li>
  );
}

function formatDuration(s: number) {
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}:${String(s % 60).padStart(2, "0")}` : `0:${String(s).padStart(2, "0")}`;
}
