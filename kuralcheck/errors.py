"""Error analysis helpers: which reference words Prisma gets wrong, and as what.
Used on the dev split to decide what goes into bias_words.txt and variants.csv.
"""

from collections import Counter
from collections.abc import Iterable
from typing import Any

import jiwer


def word_substitutions(ref: str, hyp: str) -> list[tuple[str, str]]:
    """(reference words, hypothesis words) for each substituted span; inputs already normalised."""
    if not ref or not hyp:
        return []
    out = jiwer.process_words(ref, hyp)
    ref_words, hyp_words = ref.split(), hyp.split()
    pairs = []
    for chunk in out.alignments[0]:
        if chunk.type == "substitute":
            pairs.append(
                (
                    " ".join(ref_words[chunk.ref_start_idx : chunk.ref_end_idx]),
                    " ".join(hyp_words[chunk.hyp_start_idx : chunk.hyp_end_idx]),
                )
            )
    return pairs


def top_substitutions(records: Iterable[dict[str, Any]], n: int = 30) -> list[tuple[str, str, int]]:
    counts: Counter[tuple[str, str]] = Counter()
    for r in records:
        if r.get("error") is None:
            counts.update(word_substitutions(r["ref_used"], r["hyp_norm"]))
    return [(ref, hyp, c) for (ref, hyp), c in counts.most_common(n)]


def errors_markdown(records: list[dict[str, Any]], top_n: int = 40) -> str:
    """Worst utterances (by CER) and most frequent word substitutions, for the README/app and tuning."""
    ok = [r for r in records if r.get("error") is None and r["char_ref"]]
    worst = sorted(ok, key=lambda r: r["char_edits"] / r["char_ref"], reverse=True)[:top_n]
    lines = ["# Error list", "", f"{len(ok)} scored records. Worst {len(worst)} by CER:", ""]
    lines += ["| utt | cond | setting | CER | reference | hypothesis |", "|---|---|---|---|---|---|"]
    for r in worst:
        cer = r["char_edits"] / r["char_ref"]
        lines.append(
            f"| {r['utt_id']} | {r['condition']} | {r['setting']} | {cer:.2f} | {r['ref_used']} | {r['hyp_norm']} |"
        )
    lines += ["", "## Most frequent word substitutions (reference → heard as)", ""]
    lines += ["| reference | heard as | count |", "|---|---|---|"]
    for ref, hyp, c in top_substitutions(ok):
        lines.append(f"| {ref} | {hyp} | {c} |")
    return "\n".join(lines) + "\n"
