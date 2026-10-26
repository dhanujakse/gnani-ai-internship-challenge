"""Tune the fix layer from the latest DEV run (never the test split).

    uv run python scripts/tune_fixlayer.py bias     # F2 hint words from dev F1 errors -> bias_words.txt
    uv run python scripts/tune_fixlayer.py rules    # F3 format + word rules -> format_rules.csv, variants.csv

After `bias`, re-run the dev benchmark so F2 uses the new hint words, then run `rules`.
`rules` also checks the hint words: if dev F2 is not better than F1, it empties bias_words.txt.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kuralcheck.fixlayer.bias import BIAS_WORDS_TXT  # noqa: E402
from kuralcheck.fixlayer.lexicon import FORMAT_RULES_CSV, VARIANTS_CSV  # noqa: E402
from kuralcheck.fixlayer.tune import mine_bias_words, tune_rules  # noqa: E402
from kuralcheck.report.runs import latest  # noqa: E402

BIAS_HEADER = (
    "# Prisma bias_list for setting F2: one word per line, letters only, max 100 words.\n"
    "# Auto-tuned on the DEV split by scripts/tune_fixlayer.py ({run}). Never tune on test.\n"
)


def dev_cer(records: list[dict], setting: str) -> float:
    ok = [r for r in records if r.get("error") is None and r["setting"] == setting]
    return sum(r["char_edits"] for r in ok) / max(1, sum(r["char_ref"] for r in ok))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=["bias", "rules"])
    args = p.parse_args()

    run = latest("dev")
    if run is None:
        print("No dev run in results/: run scripts/run_benchmark.py --split dev first.")
        return 1
    records = run.records()
    print(f"Using {run.name} ({len(records)} records, dev split)")

    if args.step == "bias":
        words = mine_bias_words(records)
        BIAS_WORDS_TXT.write_text(BIAS_HEADER.format(run=run.name) + "\n".join(words) + "\n", encoding="utf-8")
        print(f"Wrote {len(words)} hint words to data/lexicon/bias_words.txt: {', '.join(words[:15])}"
              + (" …" if len(words) > 15 else ""))  # fmt: skip
        print("Next: uv run python scripts/run_benchmark.py --split dev   (F2 now uses these words)")
        return 0

    f1, f2 = dev_cer(records, "F1"), dev_cer(records, "F2")
    base = "F2"
    print(f"Dev CER: F1 {100 * f1:.2f}%  F2 {100 * f2:.2f}%")
    if f2 >= f1:
        print("Hint words did not help on dev: emptying bias_words.txt (F2 = F1).")
        BIAS_WORDS_TXT.write_text(BIAS_HEADER.format(run=run.name) + "# (no words: boosting did not help on dev)\n",
                                  encoding="utf-8")  # fmt: skip
        base = "F1"
    lex, report = tune_rules(records, base_setting=base)
    with FORMAT_RULES_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["pattern", "replacement", "note"])
        for fr in report.format_kept:
            w.writerow([fr.pattern, fr.replacement, f"{fr.note} (auto-tuned on {run.name})"])
    with VARIANTS_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["pattern", "replacement", "category"])
        w.writerow([f"# Auto-tuned on the DEV split ({run.name}) by scripts/tune_fixlayer.py", "", ""])
        for rule in report.word_kept:
            w.writerow([rule.pattern, rule.replacement, "auto"])
    print(f"Dev character edits on {base}: {report.base_edits} -> {report.final_edits} with the fix layer")
    print(f"Kept {len(report.format_kept)} format rules: " + "; ".join(fr.note for fr in report.format_kept))
    print(f"Kept {len(report.word_kept)} word rules: " + ", ".join(f"{r.pattern}->{r.replacement}" for r in report.word_kept))
    if report.rejected:
        print(f"Rejected {len(report.rejected)} candidates that did not help or hurt a record.")
    print("Next: uv run python scripts/run_benchmark.py --split dev   (0 new calls; F3 uses the new rules)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
