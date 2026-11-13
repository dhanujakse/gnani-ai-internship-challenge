// The always-on app socket (/v1/chat/ws), as kept open by the Android app while signed in.
// The web uses it for ringing: incoming_call, call_answered / declined / missed / busy, call_cancelled.

import { WS_URL } from "./api";

export type AppEvent = { type: string; [k: string]: unknown };

/** `renewAuth` refreshes the access token (resolves false when the session is gone). */
export function openAppSocket(token: () => string, onEvent: (e: AppEvent) => void, renewAuth: () => Promise<boolean>) {
  let ws: WebSocket | null = null;
  let stopped = false;
  let attempt = 0;
  let ping: ReturnType<typeof setInterval> | null = null;

  const connect = () => {
    if (stopped) return;
    const sock = new WebSocket(`${WS_URL}/v1/chat/ws`, ["sarvagyan.v1", `auth.${token()}`]);
    ws = sock;
    sock.onopen = () => {
      attempt = 0;
      ping = setInterval(() => sock.readyState === WebSocket.OPEN && sock.send(JSON.stringify({ type: "ping", t: Date.now() })), 25000);
    };
    sock.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      let e: AppEvent;
      try {
        e = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (e.type === "call_state" && e.ack_id) {
        sock.send(JSON.stringify({ type: "call_ack", call_id: e.call_id, state: e.state, ack_id: e.ack_id }));
      }
      onEvent(e);
    };
    sock.onclose = (ev) => {
      if (ping) clearInterval(ping);
      ping = null;
      if (stopped) return;
      attempt += 1;
      if (ev.code === 4401) {
        // access tokens last 15 minutes: renew, then reconnect
        renewAuth().then((ok) => ok && !stopped && connect());
        return;
      }
      setTimeout(connect, Math.min(15000, 1000 * 2 ** Math.min(attempt, 4)));
    };
  };

  connect();
  return () => {
    stopped = true;
    if (ping) clearInterval(ping);
    ws?.close();
  };
}
