"""Development test peer: a scripted second participant for testing with ONE phone or emulator.

It signs in as a demo user, joins (or creates) a call, streams a recorded voice clip at real-time
cadence exactly like the app does, and prints every translation it receives. It does NOT do WebRTC,
so the phone will show the original-voice connection as not connected; the translation path
(speech recognition -> translation -> translated voice + subtitles) is fully exercised.

    # phone creates the call and shows a code; then:
    uv run python tools/test_peer.py --join ABC234 --language en-IN --say tests/fixtures/en_call_back_pranav.wav
    # or let the bot create the call and type its code into the phone:
    uv run python tools/test_peer.py --create --language ta-IN --say tests/fixtures/ta_holiday_asmita.wav --repeat 3
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
import websockets


def frames(path: Path) -> list[bytes]:
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = x.mean(axis=1)
    if sr != 16000:  # simple resample for test clips
        idx = np.linspace(0, len(mono) - 1, int(len(mono) * 16000 / sr))
        mono = np.interp(idx, np.arange(len(mono)), mono)
    pcm = (np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes() + bytes(32000)  # 1 s silence ends the turn
    return [pcm[i:i + 1024].ljust(1024, b"\0") for i in range(0, len(pcm), 1024)]


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://127.0.0.1:8787")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--join", metavar="CODE")
    g.add_argument("--create", action="store_true")
    p.add_argument("--language", default="en-IN")
    p.add_argument("--say", type=Path, help="WAV clip the bot speaks after the other person joins")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--name", default="Test peer (bot)")
    args = p.parse_args()

    async with httpx.AsyncClient(base_url=args.server, timeout=15) as http:
        session = (await http.post("/v1/auth/demo", json={"display_name": args.name})).raise_for_status().json()
        auth = {"Authorization": f"Bearer {session['token']}"}
        if args.create:
            call = (await http.post("/v1/calls", json={"language": args.language}, headers=auth)).raise_for_status().json()
            print(f"Created call. Enter this code in the app:  {call['invite_code']}")
        else:
            r = await http.post("/v1/calls/join", json={"code": args.join, "language": args.language}, headers=auth)
            if r.status_code != 200:
                print(f"Join failed: {r.status_code} {r.text}")
                return 1
            call = r.json()
    me = session["user"]["id"]
    ws_url = args.server.replace("https://", "wss://").replace("http://", "ws://") + f"/v1/calls/{call['call_id']}/ws"
    clip = frames(args.say) if args.say else []
    async with websockets.connect(ws_url, additional_headers=auth, max_size=None) as ws:
        await ws.send(json.dumps({"type": "hello", "language": args.language}))
        peer_here = asyncio.Event()
        audio_bytes = 0

        async def speak() -> None:
            await peer_here.wait()
            await asyncio.sleep(4)
            for n in range(args.repeat):
                print(f"[bot] speaking clip {n + 1}/{args.repeat} ({len(clip) * 0.032:.1f} s)")
                for f in clip:
                    await ws.send(f)
                    await asyncio.sleep(0.032)
                await asyncio.sleep(6)

        speaker = asyncio.create_task(speak()) if clip else None
        async for raw in ws:
            if isinstance(raw, bytes):
                audio_bytes += len(raw)
                continue
            m = json.loads(raw)
            t = m.get("type")
            if t == "peer_joined":
                print(f"[call] {m['peer']['name']} joined ({m['peer']['language']})")
                peer_here.set()
            elif t == "utterance" and m["stage"] in ("translated", "failed", "skipped", "done"):
                who = "bot" if m["speaker_id"] == me else "app user"
                print(f"[{m['stage']:>10}] {who}: '{m['original']}' -> '{m.get('translation')}' {m.get('metrics', {})}"
                      + (f" ERROR {m['error']}" if m.get("error") else ""))
            elif t == "tts_end":
                print(f"[voice] received {audio_bytes / 32000:.1f} s of translated speech")
                audio_bytes = 0
            elif t in ("error", "notice"):
                print(f"[{t}] {m.get('message')}")
            elif t == "peer_left":
                print("[call] the other person left")
                break
        if speaker:
            speaker.cancel()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass
