"""Post-processing lexicon (setting F3): rules from data/lexicon/variants.csv.

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
_WORD_CHAR = r"[\w஀-௿‌‍]"  # \w misses Tamil vowel signs and pulli
_SPACES = re.compile(r"[ \t]{2,}")


@dataclass(frozen=True)
class Rule:
    pattern: str
    replacement: str
    category: str


class Lexicon:
    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules
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
        if self._re is None:
            return text, []
        hits: list[str] = []

        def repl(m: re.Match[str]) -> str:
            hits.append(m.group(0))
            return self._map[m.group(0).casefold()]

        out = self._re.sub(repl, text)
        return _SPACES.sub(" ", out).strip(), hits

    def apply(self, text: str) -> str:
        return self.apply_with_hits(text)[0]


def load_lexicon(path: Path = VARIANTS_CSV) -> Lexicon:
    if not path.exists():
        return Lexicon([])
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
    return Lexicon(rules)
