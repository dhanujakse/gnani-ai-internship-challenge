"""Prisma bias_list (setting F2): words from data/lexicon/bias_words.txt, one per line.

Lines starting with # are comments. Duplicates are dropped. The list is validated locally
(single words, letters only, <= 100) because Prisma silently ignores an invalid list.
Tune this file on split=dev only.
"""

import hashlib
import unicodedata
from pathlib import Path

from kuralcheck.clients.prisma import validate_bias_list
from kuralcheck.data import LEXICON_DIR

BIAS_WORDS_TXT = LEXICON_DIR / "bias_words.txt"


def load_bias_words(path: Path = BIAS_WORDS_TXT) -> tuple[str, ...]:
    if not path.exists():
        return ()
    words: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        w = unicodedata.normalize("NFC", line.strip())
        if w and not w.startswith("#") and w not in words:
            words.append(w)
    return tuple(validate_bias_list(words))


def file_sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else None
