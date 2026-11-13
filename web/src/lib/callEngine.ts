// Browser side of a Sarvagyan call: the web counterpart of the app's CallSession + MicPipeline + EchoGate +
// TranslatedAudioPlayer. Protocol: /v1/calls/{id}/ws (see server realtime.py).
//  - mic: 16 kHz mono s16le, exactly 1,024-byte frames at real-time cadence
//  - echo gate: while translated speech plays, send silence frames so it is never re-recognised
//  - translated speech arrives as raw 16 kHz PCM; played in order, one chunk after another
//  - utterance events are upserted by id; a lower `rev` than the one shown is ignored
// The original voice (WebRTC) is not carried on the web: you hear the translation and read subtitles.

import { WS_URL } from "./api";

export const SAMPLE_RATE = 16000;
const FRAME_SAMPLES = 512; // 1,024 bytes
const PROTOCOL = "sarvagyan.v1";

export type Stage = "listening" | "recognized" | "translating" | "translated" | "speaking" | "done" | "failed" | "skipped";

export interface Turn {
  id: string;
  speakerId: string;
  seq: number;
  rev: number;
  stage: Stage;
  original: string;
  translation: string | null;
  sourceLang: string;
  targetLang: string | null;
  error: string | null;
  delayMs: number | null;
}

export interface Participant {
  user_id: string;
  name: string;
  language: string;
  avatar?: string | null;
  muted?: boolean;
  connected?: boolean;
}

export type CallStatus = "connecting" | "waiting" | "connected" | "reconnecting" | "ended";

export interface CallState {
  status: CallStatus;
  you: Participant | null;
  peer: Participant | null;
  turns: Turn[];
  meSpeaking: boolean;
  peerSpeaking: boolean;
  muted: boolean;
  playing: boolean;
  micReady: boolean;
  notice: string | null;
  error: string | null;
  endReason: string | null;
  startedAt: number | null;
  endedAt: number | null;
}

export const initialCallState = (): CallState => ({
  status: "connecting",
  you: null,
  peer: null,
  turns: [],
  meSpeaking: false,
  peerSpeaking: false,
  muted: false,
  playing: false,
  micReady: false,
  notice: null,
  error: null,
  endReason: null,
  startedAt: null,
  endedAt: null,
});

export class CallEngine {
  private state: CallState = initialCallState();
  private ws: WebSocket | null = null;
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private proc: ScriptProcessorNode | null = null;
  private pending: number[] = [];
  private resamplePos = 0;
  private playhead = 0;
  private leaving = false;
  private retries = 0;
  private ping: ReturnType<typeof setInterval> | null = null;
  private noticeTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private callId: string,
    private token: () => string,
    private language: string,
    private myId: string,
    private onChange: (s: CallState) => void,
    private renewAuth: () => Promise<boolean>,
  ) {}
  private renewed = false;

  get snapshot() {
    return this.state;
  }

  private set(patch: Partial<CallState>) {
    this.state = { ...this.state, ...patch };
    this.onChange(this.state);
  }

  async start() {
    const ctx = new AudioContext();
    this.ctx = ctx;
    await ctx.resume().catch(() => undefined);
    if (this.leaving) return; // closed while the audio device was starting
    this.openSocket();
    await this.startMic();
  }

  // ---------- socket ----------

  private openSocket() {
    // Browsers can't send an Authorization header on a WebSocket; the token rides in the subprotocol, never the URL.
    const ws = new WebSocket(`${WS_URL}/v1/calls/${this.callId}/ws`, [PROTOCOL, `auth.${this.token()}`]);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => {
      this.retries = 0;
      this.renewed = false;
      ws.send(JSON.stringify({ type: "hello", language: this.language, muted: this.state.muted }));
      this.ping ??= setInterval(() => this.sendJson({ type: "ping", t: Date.now() }), 20000);
    };
    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        try {
          this.handle(JSON.parse(ev.data));
        } catch {
          /* ignore malformed */
        }
      } else {
        this.play(ev.data as ArrayBuffer);
      }
    };
    ws.onclose = (ev) => {
      if (this.ws !== ws) return;
      this.ws = null;
      if (this.leaving || this.state.status === "ended") return;
      if (ev.code === 4401) {
        if (this.renewed) return this.finish("Please sign in again.");
        this.renewed = true; // access tokens last 15 minutes: renew once and rejoin
        this.set({ status: "reconnecting" });
        this.renewAuth().then((ok) => (ok && !this.leaving ? this.openSocket() : this.finish("Please sign in again.")));
        return;
      }
      if (ev.code === 4404) return this.finish("That call has ended, or the invitation code is no longer valid.");
      if (ev.code === 4400) return this.finish("Call failed");
      // the server keeps our seat for 30 s: try to come back, like the app does
      if (this.retries < 4) {
        this.retries += 1;
        this.set({ status: "reconnecting" });
        setTimeout(() => !this.leaving && this.openSocket(), 1500 * this.retries);
      } else {
        this.finish("No connection to the server. Check your internet and try again.");
      }
    };
  }

  private sendJson(o: object) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(o));
  }

  private handle(m: Record<string, unknown>) {
    switch (m.type) {
      case "joined": {
        const peer = (m.peer as Participant | null) ?? null;
        this.set({
          you: m.you as Participant,
          peer,
          status: peer?.connected ? "connected" : "waiting",
          startedAt: peer?.connected ? (this.state.startedAt ?? Date.now()) : this.state.startedAt,
        });
        break;
      }
      case "peer_joined":
        this.set({ peer: m.peer as Participant, status: "connected", startedAt: this.state.startedAt ?? Date.now() });
        break;
      case "participant": {
        const p = m.participant as Participant;
        if (p.user_id === this.myId) this.set({ you: p });
        else this.set({ peer: p });
        break;
      }
      case "peer_reconnecting":
        this.set({ status: "reconnecting", peerSpeaking: false });
        this.flash(`${this.state.peer?.name ?? "They"} lost connection — waiting for them…`);
        break;
      case "peer_left":
        this.finish(`${this.state.peer?.name ?? "The other person"} left the call.`);
        break;
      case "speech_activity":
        if (m.speaker_id === this.myId) this.set({ meSpeaking: Boolean(m.active) });
        else this.set({ peerSpeaking: Boolean(m.active) });
        break;
      case "utterance":
        this.upsert(m);
        break;
      case "notice":
        if (m.code !== "peer_unavailable") this.flash(String(m.message ?? ""));
        break;
      case "error":
        this.set({ error: String(m.message ?? "Something went wrong.") });
        if (m.retryable === false && m.scope === "call" && m.code === "full") this.finish("That call already has two people.");
        break;
      case "tts_start":
        this.set({ playing: true });
        break;
      case "tts_end":
        // playback may still be running from the queue; the gate follows the real playhead
        break;
    }
  }

  private upsert(m: Record<string, unknown>) {
    const id = String(m.id);
    const rev = Number(m.rev ?? 0);
    const metrics = (m.metrics as Record<string, number> | undefined) ?? {};
    const turn: Turn = {
      id,
      speakerId: String(m.speaker_id),
      seq: Number(m.seq ?? 0),
      rev,
      stage: String(m.stage) as Stage,
      original: String(m.original ?? ""),
      translation: (m.translation as string | null) ?? null,
      sourceLang: String(m.source_lang ?? ""),
      targetLang: (m.target_lang as string | null) ?? null,
      error: (m.error as string | null) ?? null,
      delayMs: metrics.server_total_ms ?? metrics.translate_ms ?? null,
    };
    const turns = this.state.turns;
    const i = turns.findIndex((t) => t.id === id);
    if (i >= 0) {
      if (turns[i].rev > rev) return; // forward-only
      const next = turns.slice();
      next[i] = turn;
      this.set({ turns: next });
    } else {
      this.set({ turns: [...turns, turn].sort((a, b) => a.seq - b.seq) });
    }
  }

  private flash(text: string) {
    if (!text) return;
    if (this.noticeTimer) clearTimeout(this.noticeTimer);
    this.set({ notice: text });
    this.noticeTimer = setTimeout(() => this.set({ notice: null }), 5000);
  }

  // ---------- microphone ----------

  private async startMic() {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch {
      if (!this.leaving) this.set({ error: "Microphone needed. Allow microphone access in your browser to speak in this call." });
      return;
    }
    const ctx = this.ctx;
    if (this.leaving || !ctx) {
      // the call ended while the browser was asking for the microphone
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    this.stream = stream;
    const src = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    const sink = ctx.createGain();
    sink.gain.value = 0; // keeps the processor running without playing the mic back
    proc.onaudioprocess = (e) => this.capture(e.inputBuffer.getChannelData(0), ctx.sampleRate);
    src.connect(proc);
    proc.connect(sink);
    sink.connect(ctx.destination);
    this.proc = proc;
    this.set({ micReady: true });
  }

  private capture(input: Float32Array, rate: number) {
    // linear resample to 16 kHz, carrying the fractional position across buffers
    const step = rate / SAMPLE_RATE;
    let pos = this.resamplePos;
    while (pos < input.length - 1) {
      const i = Math.floor(pos);
      const f = pos - i;
      this.pending.push(input[i] * (1 - f) + input[i + 1] * f);
      pos += step;
    }
    this.resamplePos = pos - input.length;

    const ws = this.ws;
    // echo gate: silence while translated speech is playing, and while muted
    const gate = this.state.muted || this.isPlaying();
    while (this.pending.length >= FRAME_SAMPLES) {
      const chunk = this.pending.splice(0, FRAME_SAMPLES);
      if (!ws || ws.readyState !== WebSocket.OPEN) continue;
      const pcm = new Int16Array(FRAME_SAMPLES);
      if (!gate) {
        for (let k = 0; k < FRAME_SAMPLES; k++) {
          const s = Math.max(-1, Math.min(1, chunk[k]));
          pcm[k] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
      }
      ws.send(pcm.buffer);
    }
  }

  // ---------- translated speech ----------

  private isPlaying() {
    return !!this.ctx && this.playhead > this.ctx.currentTime + 0.05;
  }

  private play(buf: ArrayBuffer) {
    const ctx = this.ctx;
    if (!ctx || buf.byteLength < 2) return;
    const pcm = new Int16Array(buf, 0, Math.floor(buf.byteLength / 2));
    const audio = ctx.createBuffer(1, pcm.length, SAMPLE_RATE);
    const ch = audio.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768;
    const node = ctx.createBufferSource();
    node.buffer = audio;
    node.connect(ctx.destination);
    const at = Math.max(ctx.currentTime + 0.03, this.playhead);
    node.start(at);
    this.playhead = at + audio.duration;
    this.set({ playing: true });
    node.onended = () => {
      if (!this.isPlaying()) this.set({ playing: false });
    };
  }

  // ---------- controls ----------

  setMuted(muted: boolean) {
    this.set({ muted });
    this.sendJson({ type: "settings", muted });
  }

  setLanguage(language: string) {
    this.language = language;
    this.sendJson({ type: "settings", language });
  }

  retry(id: string) {
    this.sendJson({ type: "retry", id });
  }

  hangUp() {
    this.leaving = true;
    this.sendJson({ type: "leave" });
    this.finish("Call ended");
  }

  private finish(reason: string) {
    if (this.state.status === "ended") return;
    this.cleanup();
    this.set({ status: "ended", endReason: reason, endedAt: Date.now(), meSpeaking: false, peerSpeaking: false, playing: false });
  }

  cleanup() {
    this.leaving = true;
    if (this.ping) clearInterval(this.ping);
    this.ping = null;
    try {
      this.ws?.close();
    } catch {
      /* already closed */
    }
    this.ws = null;
    this.proc?.disconnect();
    this.proc = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.ctx?.close().catch(() => undefined);
    this.ctx = null;
  }
}
