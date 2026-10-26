"""Post-processing fix layer (setting F3).

1. Format rules from data/lexicon/format_rules.csv (regex: pattern, replacement, note), applied
   first, in file order, e.g. "₹25" -> "25 ரூபாய்", "03:40" -> "3:40".
2. Word rules from data/lexicon/variants.csv, described below.

Word rules: from data/lexicon/variants.csv.

Columns: pattern, replacement, category. Rules are applied in a single pass,
longest pattern first, on whole words only. A Tamil vowel sign or pulli right next
to a match means it is inside a longer word, so the rule does not fire.
Latin letters match case-insensitively. Rows starting with # are comments.
Tune this file on split=dev only.
"""

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from kuralcheck.data import LEXICON_DIR

VARIANTS_CSV = LEXICON_DIR / "variants.csv"
FORMAT_RULES_CSV = LEXICON_DIR / "format_rules.csv"
_WORD_CHAR = r"[\w\u0b80-\u0bff\u200c\u200d]"  # \w misses Tamil vowel signs and pulli
_SPACES = re.compile(r"[ \t]{2,}")


@dataclass(frozen=True)
class Rule:
    pattern: str
    replacement: str
    category: str


@dataclass(frozen=True)
class FormatRule:
    pattern: str  # Python regex
    replacement: str  # may use \1 groups
    note: str = ""

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern)


class Lexicon:
    def __init__(self, rules: list[Rule], format_rules: list[FormatRule] | None = None) -> None:
        self.rules = rules
        self.format_rules = list(format_rules or [])
        self._format = [(r.compiled(), r.replacement) for r in self.format_rules]
        self._map = {unicodedata.normalize("NFC", r.pattern).casefold(): r.replacement for r in rules}
        if rules:
            alternation = "|".join(
                re.escape(unicodedata.normalize("NFC", r.pattern))
                for r in sorted(rules, key=lambda r: len(r.pattern), reverse=True)
            )
            self._re: re.Pattern[str] | None = re.compile(
                rf"(?<!{_WORD_CHAR})(?:{alternation})(?!{_WORD_CHAR})", re.IGNORECASE
            )
        else:
            self._re = None

    def apply_with_hits(self, text: str) -> tuple[str, list[str]]:
        text = unicodedata.normalize("NFC", text)
        hits: list[str] = []
        for rx, repl_text in self._format:
            text, n = rx.subn(repl_text, text)
            hits += [f"format:{rx.pattern}"] * n
        if self._re is None:
            return _SPACES.sub(" ", text).strip(), hits

        def repl(m: re.Match[str]) -> str:
            hits.append(m.group(0))
            return self._map[m.group(0).casefold()]

        out = self._re.sub(repl, text)
        return _SPACES.sub(" ", out).strip(), hits

    def apply(self, text: str) -> str:
        return self.apply_with_hits(text)[0]


def load_format_rules(path: Path = FORMAT_RULES_CSV) -> list[FormatRule]:
    if not path.exists():
        return []
    out: list[FormatRule] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            pattern = (row.get("pattern") or "").strip()
            if not pattern or pattern.startswith("#"):
                continue
            rule = FormatRule(pattern, row.get("replacement") or "", (row.get("note") or "").strip())
            try:
                rule.compiled()
            except re.error as exc:
                raise ValueError(f"{path.name} line {line_no}: bad regex '{pattern}': {exc}") from None
            out.append(rule)
    return out


def load_lexicon(path: Path = VARIANTS_CSV, format_path: Path | None = None) -> Lexicon:
    fmt = load_format_rules(format_path if format_path is not None else (path.parent / FORMAT_RULES_CSV.name))
    if not path.exists():
        return Lexicon([], fmt)
    rules: list[Rule] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            pattern = (row.get("pattern") or "").strip()
            if not pattern or pattern.startswith("#"):
                continue
            key = unicodedata.normalize("NFC", pattern).casefold()
            if key in seen:
                raise ValueError(f"{path.name} line {line_no}: duplicate pattern '{pattern}'")
            seen.add(key)
            rules.append(Rule(pattern, (row.get("replacement") or "").strip(), (row.get("category") or "").strip()))
    return Lexicon(rules, fmt)
