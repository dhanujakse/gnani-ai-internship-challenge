"""One real Timbre + Prisma round trip to check the key, then a repeat that must hit the cache.

    uv run python scripts/smoke_api.py                 # Timbre speaks a sentence, Prisma transcribes it
    uv run python scripts/smoke_api.py --wav my.wav    # transcribe your own WAV instead

At most 2 paid calls the first time, 0 after that.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck.cache import Cache  # noqa: E402
from kuralcheck.clients.errors import ApiError  # noqa: E402
from kuralcheck.clients.prisma import PrismaClient, PrismaSettings  # noqa: E402
from kuralcheck.clients.timbre import TimbreClient, TimbreSettings  # noqa: E402
from kuralcheck.config import get_settings  # noqa: E402

SENTENCE = "நாளைக்கு காலையில பத்து மணிக்கு கடைக்கு வாங்க"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", type=Path, help="your own WAV file (otherwise Timbre makes one)")
    args = parser.parse_args()

    settings = get_settings()
    cache = Cache(settings.cache_path)
    try:
        prisma = PrismaClient.from_settings(settings, cache)
        if args.wav:
            audio, name = args.wav.read_bytes(), args.wav.name
        else:
            timbre = TimbreClient.from_settings(settings, cache)
            tts = timbre.synthesize(SENTENCE, TimbreSettings(voice="Trisha", model=settings.tts_model))
            out = Path("cache/smoke_trisha.wav")
            out.write_bytes(tts.audio)
            print(f"Timbre: {len(tts.audio):,} bytes, {tts.latency_ms:.0f} ms, cached={tts.cached} -> {out}")
            print(f"  text:       {SENTENCE}")
            audio, name = tts.audio, "smoke.wav"

        s = PrismaSettings(format="verbatim")
        first = prisma.transcribe(audio, name, s)
        print(f"Prisma: {first.latency_ms:.0f} ms, cached={first.cached}")
        print(f"  transcript: {first.transcript}")
        second = prisma.transcribe(audio, name, s)
        print(f"Repeat: cached={second.cached}  ({'OK, no new call' if second.cached else 'CACHE MISS'})")
        return 0 if second.cached else 1
    except (ApiError, ValueError) as exc:
        print(f"Failed: {exc}")
        return 1
    finally:
        cache.close()


if __name__ == "__main__":
    sys.exit(main())
