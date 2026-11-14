"use client";

import type { ReactNode } from "react";
import type { Language, User } from "@/lib/api";
import { Avatar, Brand, Icon, LanguagePill, StatusChip, langLabel, type IconName } from "./ui";

export type Tab = "home" | "contacts" | "settings" | "help";

const NAV: { tab: Tab; icon: IconName; label: string }[] = [
  { tab: "home", icon: "home", label: "Home" },
  { tab: "contacts", icon: "people", label: "Contacts" },
  { tab: "settings", icon: "settings", label: "Settings" },
  { tab: "help", icon: "help", label: "Help & Manual" },
];

/** Desktop: the app's navigation drawer as a permanent sidebar. Phones: a bottom bar. */
export function Shell({
  user,
  languages,
  online,
  tab,
  onTab,
  onSignOut,
  children,
}: {
  user: User;
  languages: Language[];
  online: boolean | null;
  tab: Tab;
  onTab: (t: Tab) => void;
  onSignOut: () => void;
  children: ReactNode;
}) {
  return (
    <div className="sg-app-bg flex min-h-dvh">
      <aside className="sticky top-0 hidden h-dvh w-[280px] shrink-0 flex-col border-r border-line/60 bg-bg2/85 backdrop-blur-md lg:flex">
        <div className="px-5 py-5">
          <Brand />
        </div>
        <div className="mx-4 rounded-lg border border-line bg-card p-4">
          <Avatar name={user.display_name} avatar={user.avatar} size={56} />
          <p className="mt-3 truncate text-[18px] font-semibold text-ink">{user.display_name}</p>
          {user.username && <p className="truncate text-[14px] text-highlight">@{user.username}</p>}
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <LanguagePill highlighted>{langLabel(languages, user.language)}</LanguagePill>
            {user.is_demo && <StatusChip tone="warning">Demo account</StatusChip>}
          </div>
        </div>
        <nav className="mt-4 flex-1 space-y-1 px-3" aria-label="Main">
          {NAV.map((n) => (
            <button
              key={n.tab}
              type="button"
              onClick={() => onTab(n.tab)}
              aria-current={tab === n.tab ? "page" : undefined}
              className={`flex w-full items-center gap-3 rounded-full px-4 py-3 text-[15px] font-medium transition-colors ${
                tab === n.tab ? "bg-elevated text-ink" : "text-sub hover:bg-card hover:text-ink"
              }`}
            >
              <Icon name={n.icon} className={tab === n.tab ? "text-highlight" : ""} />
              {n.label}
            </button>
          ))}
        </nav>
        <div className="border-t border-line/60 p-3">
          <div className="px-4 pb-2">
            <ConnectionChip online={online} />
          </div>
          <button
            type="button"
            onClick={onSignOut}
            className="flex w-full items-center gap-3 rounded-full px-4 py-3 text-[15px] font-medium text-[#ff6b81] transition-colors hover:bg-danger/10"
          >
            <Icon name="logout" />
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-line/60 bg-bg/95 px-4 backdrop-blur lg:hidden">
          <Brand size={28} />
          <ConnectionChip online={online} />
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-28 pt-6 sm:px-6 lg:px-10 lg:pb-12 lg:pt-10">{children}</main>
        <nav className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 border-t border-line/60 bg-bg2 lg:hidden" aria-label="Main">
          {NAV.map((n) => (
            <button
              key={n.tab}
              type="button"
              onClick={() => onTab(n.tab)}
              aria-current={tab === n.tab ? "page" : undefined}
              className={`flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium ${tab === n.tab ? "text-highlight" : "text-sub"}`}
            >
              <Icon name={n.icon} size={22} />
              {n.label === "Help & Manual" ? "Help" : n.label}
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}

function ConnectionChip({ online }: { online: boolean | null }) {
  if (online === null) return <StatusChip pulsing>Checking…</StatusChip>;
  return online ? <StatusChip tone="success">Connected</StatusChip> : <StatusChip tone="error">Offline</StatusChip>;
}
