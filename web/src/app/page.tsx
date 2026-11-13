"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import {
  Api,
  ApiError,
  FALLBACK_LANGUAGES,
  loadSession,
  normaliseCode,
  saveSession,
  sessionSnapshot,
  subscribeSession,
  type Language,
  type Session,
  type User,
} from "@/lib/api";
import { openAppSocket, type AppEvent } from "@/lib/appSocket";
import { CallScreen, Dialog, type ActiveCall } from "@/components/CallScreen";
import { Contacts } from "@/components/Contacts";
import { Home } from "@/components/Home";
import { Landing } from "@/components/Landing";
import { Help, Settings } from "@/components/Settings";
import { Shell, type Tab } from "@/components/Shell";
import { Avatar, Logo, PrimaryButton, TextButton, langLabel } from "@/components/ui";

interface Incoming {
  callId: string;
  from: { id: string; name: string; language: string; avatar?: string | null };
}

const SERVER_SNAPSHOT = undefined; // on the server (and while hydrating) we don't know the session yet

export default function Page() {
  const session = useSyncExternalStore<Session | null | undefined>(subscribeSession, sessionSnapshot, () => SERVER_SNAPSHOT);
  const [languages, setLanguages] = useState<Language[]>(FALLBACK_LANGUAGES);
  // invitation links land here as /?code=ABC234 (via /join)
  const [pendingCode, setPendingCode] = useState(() =>
    typeof window === "undefined" ? "" : normaliseCode(new URLSearchParams(window.location.search).get("code") ?? ""),
  );
  const [tab, setTab] = useState<Tab>("home");
  const [online, setOnline] = useState<boolean | null>(null);
  const [call, setCall] = useState<ActiveCall | null>(null);
  const [incoming, setIncoming] = useState<Incoming | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // the server's language list, like the app's refreshLanguages()
  useEffect(() => {
    Api.languages()
      .then((r) => r.languages?.length && setLanguages(r.languages))
      .catch(() => undefined);
  }, []);

  const userId = session?.user.id;

  // refresh the profile and the "Connected" chip
  useEffect(() => {
    if (!userId) return;
    let alive = true;
    Api.me()
      .then((u) => {
        if (!alive) return;
        setOnline(true);
        const s = loadSession();
        if (s) saveSession({ ...s, user: u });
      })
      .catch((e) => alive && setOnline(e instanceof ApiError && e.status !== 0 ? true : false));
    return () => {
      alive = false;
    };
  }, [userId]);

  // the app socket: ringing in both directions
  useEffect(() => {
    if (!userId) return;
    return openAppSocket(
      () => loadSession()?.token ?? "",
      (e: AppEvent) => {
        const cid = String(e.call_id ?? "");
        if (e.type === "incoming_call") {
          const from = e.from as Incoming["from"];
          setIncoming({ callId: cid, from });
        } else if (e.type === "call_cancelled") {
          setIncoming((cur) => (cur?.callId === cid ? null : cur));
        } else if (["call_declined", "call_missed", "call_no_answer", "call_busy"].includes(e.type)) {
          const outcome = e.type.replace("call_", "");
          setCall((cur) => (cur && cur.callId === cid ? { ...cur, outcome } : cur));
        }
      },
      () => Api.me().then(() => true).catch(() => false),
    );
  }, [userId]);

  const updateUser = useCallback((u: User) => {
    const s = loadSession();
    if (s) saveSession({ ...s, user: u });
  }, []);

  const fail = (e: unknown, fallback: string) => setNotice(e instanceof ApiError ? e.message : fallback);

  const startCall = async () => {
    if (!session) return;
    setBusy(true);
    try {
      const info = await Api.createCall(session.user.language);
      setCall({ callId: info.call_id, code: info.invite_code, mode: "invite" });
    } catch (e) {
      fail(e, "Could not create the call.");
    } finally {
      setBusy(false);
    }
  };

  const joinCall = async (code: string) => {
    if (!session) return;
    setBusy(true);
    try {
      const info = await Api.joinCall(code, session.user.language);
      setPendingCode("");
      window.history.replaceState(null, "", "/");
      setCall({ callId: info.call_id, code: info.invite_code ?? code, mode: "joined" });
    } catch (e) {
      fail(e, "That invitation code isn't valid or has expired. Ask for a new one.");
    } finally {
      setBusy(false);
    }
  };

  const callPerson = async (id: string, name: string) => {
    if (!session) return;
    setBusy(true);
    try {
      const info = await Api.callPerson(id, session.user.language);
      if (info.call_state === "busy") return setNotice(`${name} is busy on another call.`);
      setCall({ callId: info.call_id, code: info.invite_code, mode: "outgoing", peerName: info.peer_name ?? name, reachable: info.reachable });
    } catch (e) {
      fail(e, "Could not connect the call.");
    } finally {
      setBusy(false);
    }
  };

  const answer = async (inc: Incoming) => {
    if (!session) return;
    setIncoming(null);
    try {
      const info = await Api.answer(inc.callId, session.user.language);
      setCall({ callId: info.call_id, code: info.invite_code, mode: "answered", peerName: inc.from.name });
    } catch (e) {
      fail(e, "Could not connect the call.");
    }
  };

  const decline = (inc: Incoming) => {
    setIncoming(null);
    Api.decline(inc.callId).catch(() => undefined);
  };

  const signOut = async () => {
    await Api.logout();
    saveSession(null);
    setCall(null);
    setTab("home");
  };

  if (session === undefined) {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Logo size={64} />
      </div>
    );
  }

  if (!session) {
    return (
      <Landing
        languages={languages}
        pendingCode={pendingCode}
        onSignedIn={(s) => {
          saveSession(s);
          setTab("home");
        }}
      />
    );
  }

  const user = session.user;

  if (call) {
    return <CallScreen key={call.callId} call={call} me={user} language={user.language} languages={languages} onClose={() => {
          setCall(null);
          setTab("home");
        }} />;
  }

  return (
    <>
      <Shell user={user} languages={languages} online={online} tab={tab} onTab={setTab} onSignOut={signOut}>
        {tab === "home" && (
          <Home
            user={user}
            languages={languages}
            pendingCode={pendingCode}
            busy={busy}
            onStartCall={startCall}
            onJoin={joinCall}
            onCallPerson={callPerson}
            onContacts={() => setTab("contacts")}
            onLanguage={async (code) => {
              try {
                updateUser(await Api.updateMe({ language: code }));
              } catch (e) {
                fail(e, "Couldn't change your language.");
              }
            }}
          />
        )}
        {tab === "contacts" && <Contacts user={user} languages={languages} onCall={callPerson} onUser={updateUser} />}
        {tab === "settings" && <Settings user={user} languages={languages} onUser={updateUser} onSignOut={signOut} />}
        {tab === "help" && <Help />}
      </Shell>

      {notice && (
        <Dialog title="Sarvagyan" onClose={() => setNotice(null)}>
          <p className="text-[15px] leading-6 text-sub">{notice}</p>
          <div className="mt-4 flex justify-end">
            <TextButton onClick={() => setNotice(null)}>OK</TextButton>
          </div>
        </Dialog>
      )}

      {incoming && (
        <Dialog title={incoming.from.name} onClose={() => decline(incoming)}>
          <div className="flex items-center gap-4">
            <Avatar name={incoming.from.name} avatar={incoming.from.avatar} size={64} ring />
            <p className="text-[15px] leading-6 text-sub">
              Calling you · they speak {langLabel(languages, incoming.from.language, false)}, you&apos;ll hear {langLabel(languages, user.language, false)}
            </p>
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3">
            <button type="button" onClick={() => decline(incoming)} className="min-h-[52px] rounded-md bg-danger text-[15px] font-semibold text-white hover:bg-[#d93355]">
              Decline
            </button>
            <PrimaryButton icon="call" onClick={() => answer(incoming)}>
              Accept
            </PrimaryButton>
          </div>
        </Dialog>
      )}
    </>
  );
}
