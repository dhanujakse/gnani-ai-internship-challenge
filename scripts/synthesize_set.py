"""Timbre -> data/audio/timbre/<id>__<voice>.wav for every source=timbre row (3 voices each).

    uv run python scripts/synthesize_set.py --dry-run   # just print the planned calls
    uv run python scripts/synthesize_set.py             # asks before making > 100 calls
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck import synth  # noqa: E402
from kuralcheck.budget import confirm_calls  # noqa: E402
from kuralcheck.cache import Cache  # noqa: E402
from kuralcheck.clients.timbre import TimbreClient  # noqa: E402
from kuralcheck.config import get_settings  # noqa: E402
from kuralcheck.data import load_sentences, utterances  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=["dev", "test", "all"], default="all")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()

    settings = get_settings()
    utts = [u for u in utterances(load_sentences()) if args.split in ("all", u.sentence.split)]
    jobs = synth.plan(utts, settings.tts_model)
    on_disk = sum(1 for u in utts if u.sentence.source == "timbre") - len(jobs)
    print(f"Timbre utterances: {on_disk + len(jobs)} ({on_disk} already on disk), model {settings.tts_model}")

    cache = Cache(settings.cache_path)
    try:
        client = TimbreClient.from_settings(settings, cache) if not args.dry_run or settings.gnani_api_key.get_secret_value() else None
        uncached = [j for j in jobs if client is None or not client.is_cached(j.text, j.settings)]
        if args.dry_run:
            print(f"Planned new Timbre calls: {len(uncached)} (dry run, nothing called)")
            return 0
        if not confirm_calls(len(uncached), "Timbre", yes=args.yes):
            return 1
        assert client is not None
        made, errors = synth.run(
            jobs, client, args.workers,
            progress=lambda i, n: print(f"  {i}/{n}") if i % 20 == 0 or i == n else None,
        )  # fmt: skip
        print(f"Done: {len(jobs) - len(errors)} files written, {made} new Timbre calls")
        for utt_id, err in errors:
            print(f"  FAILED {utt_id}: {err}")
        return 1 if errors else 0
    except ValueError as exc:
        print(f"Failed: {exc}")
        return 1
    finally:
        cache.close()


if __name__ == "__main__":
    sys.exit(main())
