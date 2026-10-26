"""Automatic fix-layer tuning from DEV-split results only.

bias words (F2): reference words Prisma most often gets wrong in F1 output, ranked by how often.
format rules (F3): a fixed menu of generic ITN-format rules; each is kept only if it lowers the
    total dev character edits and makes no single dev record worse (greedy, no-harm).
word rules (F3): (heard -> reference) word swaps mined from dev alignments; candidates must be
    near-identical spellings (edit ratio <= 0.4) seen >= 2 times, and pass the same no-harm test.

Nothing here reads the test split: every input record must have split == "dev".
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from kuralcheck.errors import word_substitutions
from kuralcheck.fixlayer.lexicon import FormatRule, Lexicon, Rule
from kuralcheck.metrics import score_utterance
from kuralcheck.text.normalize import normalize

MAX_BIAS_WORDS = 50  # Prisma allows 100; fewer, stronger hints are safer
MAX_EDIT_RATIO = 0.4
MIN_SUPPORT = 2

# Generic Prisma ITN formats (seen on dev) -> how references write them. Candidates, not rules:
# each one must prove itself on dev.
FORMAT_CANDIDATES = [
    FormatRule(r"₹\s*(\d(?:[\d,]*\d)?(?:\.\d+)?)", r"\1 ரூபாய்", "currency symbol -> number + ரூபாய்"),
    FormatRule(r"(?<![\d:])0(\d):(\d\d)", r"\1:\2", "drop leading zero in times (03:40 -> 3:40)"),
    FormatRule(r"(?<![\d:])(\d{1,2}):00(?!\d)", r"\1", "whole hours (10:00 -> 10)"),
    FormatRule(r"(?<![\d:])(\d{1,2}):(\d\d) மணி", r"\1 மணி \2", "H:MM மணி -> H மணி MM"),
    FormatRule(r"(?<![\d.,])1 (?=[^\d\s])", "ஒரு ", "ITN '1' for the article ஒரு"),
    FormatRule(r"(\d)%", r"\1 சதவீதம்", "percent sign -> சதவீதம்"),
]


def _check_dev(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    recs = [r for r in records if r.get("error") is None]
    bad = {r.get("split") for r in recs} - {"dev"}
    if bad:
        raise ValueError(f"tuning must use dev-split records only (got splits {sorted(bad)})")
    return recs


def char_edits(rec: dict[str, Any], hypothesis: str) -> int:
    return score_utterance(rec["reference"], hypothesis, rec["accepted_variants"]).char_edits


def edit_ratio(a: str, b: str) -> float:
    """Levenshtein distance / longer length (code points)."""
    if a == b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(len(a), len(b))


def _is_word(w: str) -> bool:
    return bool(w) and all(ch.isalpha() or not ch.isascii() for ch in w) and not any(ch.isdigit() for ch in w)


def mine_bias_words(records: Iterable[dict[str, Any]], limit: int = MAX_BIAS_WORDS) -> list[str]:
    """Reference words most often misheard in F1 output (where boosting can act)."""
    counts: Counter[str] = Counter()
    for r in _check_dev(records):
        if r["setting"] != "F1":
            continue
        for ref_span, _ in word_substitutions(r["ref_used"], r["hyp_norm"]):
            for w in ref_span.split():
                if _is_word(w) and len(w) >= 3:
                    counts[w] += 1
    return [w for w, c in counts.most_common() if c >= MIN_SUPPORT][:limit]


@dataclass
class TuneReport:
    base_edits: int = 0
    final_edits: int = 0
    format_kept: list[FormatRule] = field(default_factory=list)
    word_kept: list[Rule] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


def _total(recs: list[dict[str, Any]], lex: Lexicon) -> tuple[int, list[int]]:
    per = [char_edits(r, lex.apply(r["hypothesis_raw"])) for r in recs]
    return sum(per), per


def tune_rules(records: Iterable[dict[str, Any]], base_setting: str = "F2") -> tuple[Lexicon, TuneReport]:
    """Greedy forward selection of format rules, then word rules, on dev records of base_setting."""
    recs = [r for r in _check_dev(records) if r["setting"] == base_setting]
    report = TuneReport()
    current = Lexicon([])
    total, per = _total(recs, current)
    report.base_edits = total

    def try_add(candidate: Lexicon, label: str) -> bool:
        nonlocal current, total, per
        new_total, new_per = _total(recs, candidate)
        if new_total < total and all(n <= o for n, o in zip(new_per, per, strict=True)):
            current, total, per = candidate, new_total, new_per
            return True
        report.rejected.append(f"{label} (dev edits {total} -> {new_total})")
        return False

    for fr in FORMAT_CANDIDATES:
        if try_add(Lexicon(current.rules, [*current.format_rules, fr]), f"format {fr.note}"):
            report.format_kept.append(fr)

    # mine word swaps on the format-fixed hypotheses
    pairs: Counter[tuple[str, str]] = Counter()
    for r in recs:
        hyp = normalize(current.apply(r["hypothesis_raw"]))
        for ref_span, hyp_span in word_substitutions(r["ref_used"], hyp):
            if len(ref_span.split()) == 1 and len(hyp_span.split()) == 1 and _is_word(hyp_span):
                if edit_ratio(hyp_span, ref_span) <= MAX_EDIT_RATIO:
                    pairs[(hyp_span, ref_span)] += 1
    seen: set[str] = set()
    for (heard, ref), count in pairs.most_common():
        if count < MIN_SUPPORT or heard in seen:
            continue
        seen.add(heard)
        rule = Rule(heard, ref, "auto")
        if try_add(Lexicon([*current.rules, rule], current.format_rules), f"word {heard}->{ref} x{count}"):
            report.word_kept.append(rule)

    report.final_edits = total
    return current, report
