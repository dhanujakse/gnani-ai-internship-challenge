"use client";

import { useCallback, useEffect, useState } from "react";
import { Api, ApiError, type Contact, type Language, type User } from "@/lib/api";
import { AppCard, Avatar, EmptyState, ErrorBanner, IconButton, SectionTitle, Spinner, TextField, langLabel } from "./ui";

/** The app's Contacts screen (web): My contacts, Add by @username, Who can call me. */
export function Contacts({
  user,
  languages,
  onCall,
  onUser,
}: {
  user: User;
  languages: Language[];
  onCall: (id: string, name: string) => void;
  onUser: (u: User) => void;
}) {
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [username, setUsername] = useState("");
  const [adding, setAdding] = useState(false);
  const [addMsg, setAddMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [reloads, setReloads] = useState(0);
  const load = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    Api.contacts()
      .then((r) => {
        if (!alive) return;
        setContacts(r.contacts);
        setError(null);
      })
      .catch((e) => {
        if (!alive) return;
        setContacts((p) => p ?? []);
        setError(e instanceof ApiError ? e.message : "Couldn't load your contacts.");
      });
    return () => {
      alive = false;
    };
  }, [reloads]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const u = username.trim().replace(/^@/, "");
    if (!u) return;
    setAdding(true);
    setAddMsg(null);
    try {
      const r = await Api.addContact(u);
      setAddMsg({ ok: true, text: `Added ${r.contact.name}` });
      setUsername("");
      load();
    } catch (err) {
      setAddMsg({ ok: false, text: err instanceof ApiError && err.status !== 404 ? err.message : "No user found" });
    } finally {
      setAdding(false);
    }
  };

  const setPolicy = async (value: "everyone" | "contacts") => {
    try {
      onUser(await Api.updateMe({ allow_calls: value }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save that.");
    }
  };

  return (
    <div>
      <h1 className="mb-6 text-[26px] font-semibold text-ink">Contacts</h1>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <section>
          <SectionTitle>My Contacts</SectionTitle>
          {error && (
            <div className="mb-3">
              <ErrorBanner message={error} onRetry={load} />
            </div>
          )}
          {contacts === null ? (
            <div className="flex items-center gap-3 py-6 text-[15px] text-sub">
              <Spinner /> Loading…
            </div>
          ) : contacts.length === 0 ? (
            <EmptyState icon="people" title="No contacts yet" body="Add people by their @username to call them directly." />
          ) : (
            <ul className="divide-y divide-line/50 rounded-lg border border-line bg-card px-4">
              {contacts.map((c) => (
                <li key={c.id} className="flex items-center gap-3 py-3">
                  <Avatar name={c.name} avatar={c.avatar} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[16px] font-semibold text-ink">{c.name}</p>
                    <p className="truncate text-[14px] text-sub">
                      {c.username ? <span className="text-highlight">@{c.username}</span> : null}
                      {c.username ? " · " : ""}
                      {langLabel(languages, c.language, false)}
                      {c.is_demo ? " · demo account" : ""}
                    </p>
                  </div>
                  <IconButton icon="call" label={`Call ${c.name}`} onClick={() => onCall(c.id, c.name)} className="text-highlight" />
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="space-y-4">
          <AppCard>
            <p className="text-[16px] font-semibold text-ink">Add by @username</p>
            <form onSubmit={add} className="mt-3 space-y-3">
              <TextField
                prefix="@"
                value={username}
                onChange={(v) => setUsername(v.trim().toLowerCase())}
                placeholder="username"
                supporting={addMsg?.text}
                supportingTone={addMsg ? (addMsg.ok ? "ok" : "error") : "muted"}
              />
              <button
                type="submit"
                disabled={!username.trim() || adding}
                className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md bg-accent px-4 text-[15px] font-semibold text-ink hover:bg-[#00ad85] disabled:bg-card/60 disabled:text-sub/40"
              >
                {adding && <Spinner size={18} />}
                Add contact
              </button>
            </form>
          </AppCard>

          <AppCard>
            <p className="text-[16px] font-semibold text-ink">Who can call me</p>
            <div className="mt-3 flex gap-2" role="radiogroup" aria-label="Who can call me">
              {(
                [
                  ["everyone", "Everyone"],
                  ["contacts", "My contacts"],
                ] as const
              ).map(([value, label]) => {
                const on = (user.allow_calls ?? "contacts") === value;
                return (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    onClick={() => setPolicy(value)}
                    className={`rounded-sm border px-3.5 py-2 text-[14px] font-medium transition-colors ${on ? "border-highlight bg-highlight/10 text-ink" : "border-line text-sub hover:text-ink"}`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <p className="mt-3 text-[13px] leading-5 text-low">People you have called before can always call you back.</p>
          </AppCard>
        </aside>
      </div>
    </div>
  );
}
