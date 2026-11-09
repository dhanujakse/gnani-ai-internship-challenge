"""MyMemory translation API (mymemory.translated.net/doc/spec.php).

GET https://api.mymemory.translated.net/get?q=<text>&langpair=ta|en[&de=<email>]
- q is limited to 500 bytes (UTF-8), so longer text is split on sentence/word boundaries
- free quota: 5,000 chars/day anonymous, 50,000 with a contact email (`de`)
Response (observed live): {"responseData": {"translatedText": ...}, "responseStatus": 200, "quotaFinished": false}
A small in-memory LRU cache avoids paying twice for repeated phrases ("hello", "okay"...).

Accuracy: MyMemory returns a translation-memory match (crowd-sourced human entries) when one exists, and its own
machine translation ("created-by": "MT!") otherwise or as an extra match. Human entries for short phrases are often
unrelated to the input (probed live 30 Oct 2026), so `choose_translation` prefers the machine translation, rejects
candidates in the wrong script or of implausible length, and common call phrases never reach the API at all
(see phrasebook.py).
"""

import html
import re
from collections import OrderedDict

import httpx

from sarvagyan_server.providers import phrasebook
from sarvagyan_server.providers.base import ProviderError

API_URL = "https://api.mymemory.translated.net/get"
MAX_Q_BYTES = 480  # stay under the 500-byte limit
CACHE_SIZE = 2048
_SENTENCE = re.compile(r"(?<=[.!?।])\s+")

# Unicode block of each target language's script (Latin for English)
_SCRIPTS = {
    "ta": (0x0B80, 0x0BFF), "hi": (0x0900, 0x097F), "mr": (0x0900, 0x097F), "te": (0x0C00, 0x0C7F),
    "kn": (0x0C80, 0x0CFF), "ml": (0x0D00, 0x0D7F), "bn": (0x0980, 0x09FF), "gu": (0x0A80, 0x0AFF),
    "pa": (0x0A00, 0x0A7F), "en": (0x0041, 0x024F),
}


def in_script(text: str, lang: str) -> bool:
    """True when most letters of `text` are in the target language's script (unknown languages: always True)."""
    block = _SCRIPTS.get(lang)
    letters = [c for c in text if c.isalpha()]
    if not block or not letters:
        return bool(letters) or not block
    lo, hi = block
    return sum(lo <= ord(c) <= hi for c in letters) >= 0.6 * len(letters)


_TROLL_PATTERNS = ("ஐ லவ் யூ", "i love you", "டார்லிங்", "darling")


def plausible_length(source: str, candidate: str) -> bool:
    """Reject answers far longer or shorter than the input (a typical sign of an unrelated memory entry)."""
    s, c = len(source.strip()), len(candidate.strip())
    if s <= 5 and c > 12:
        return False
    return c <= 4 * s + 12 and c * 5 + 6 >= s


def choose_translation(source: str, target_lang: str, body: dict) -> str:
    """Pick the most trustworthy candidate from a MyMemory response.

    Order: a valid machine translation, then clean matches by match score, then the main answer.
    Valid = right script, plausible length, and free from crowdsourced vandalism/troll entries.
    """
    main = ((body.get("responseData") or {}).get("translatedText") or "").strip()
    matches = [m for m in body.get("matches") or [] if isinstance(m, dict) and (m.get("translation") or "").strip()]

    def ok(text: str) -> bool:
        text = html.unescape(text)
        src_lower = source.lower()
        cand_lower = text.lower()
        # Vandalism protection: reject romantic/troll translations when source has no such intent
        if any(tp in cand_lower or tp in text for tp in _TROLL_PATTERNS):
            if "love" not in src_lower and "darling" not in src_lower:
                return False
        return in_script(text, target_lang) and plausible_length(source, text)

    machine = [m["translation"] for m in matches if m.get("created-by") == "MT!"]
    others = [m["translation"] for m in sorted(matches, key=lambda m: -float(m.get("match") or 0))]
    for candidate in [*machine, *others, main]:
        if candidate and ok(candidate):
            return candidate.strip()
    if ok(main):
        return main
    return machine[0].strip() if machine else (source if not ok(main) else main)


def split_for_limit(text: str, max_bytes: int = MAX_Q_BYTES) -> list[str]:
    """Split into pieces under max_bytes UTF-8, preferring sentence then word boundaries."""
    pieces: list[str] = []
    for sentence in _SENTENCE.split(text.strip()):
        if len(sentence.encode()) <= max_bytes:
            pieces.append(sentence)
            continue
        current = ""
        for word in sentence.split():
            candidate = f"{current} {word}".strip()
            if len(candidate.encode()) > max_bytes and current:
                pieces.append(current)
                current = word
            else:
                current = candidate
        if current:
            pieces.append(current)
    # merge small neighbours back together to save requests
    merged: list[str] = []
    for piece in pieces:
        if merged and len(f"{merged[-1]} {piece}".encode()) <= max_bytes:
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)
    return [p for p in merged if p]


class MyMemoryTranslator:
    name = "mymemory"

    def __init__(self, email: str = "", client: httpx.AsyncClient | None = None, timeout_s: float = 6.0) -> None:
        self._email = email
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()

    async def _fallback_gtx(self, text: str, source: str, target: str) -> str | None:
        src = source.split("-")[0]
        tgt = target.split("-")[0]
        try:
            r = await self._client.get(
                "https://translate.googleapis.com/translate_a/single",
                params={"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                    translated = "".join(seg[0] for seg in data[0] if isinstance(seg, list) and len(seg) > 0 and seg[0])
                    if translated.strip():
                        return translated.strip()
        except Exception:
            pass
        return None

    async def _one(self, text: str, source: str, target: str) -> str:
        # Prefer Google Translate GTX first to avoid crowdsourced vandalism in MyMemory
        gtx_res = await self._fallback_gtx(text, source, target)
        if gtx_res:
            return gtx_res

        params = {"q": text, "langpair": f"{source.split('-')[0]}|{target.split('-')[0]}"}
        if self._email:
            params["de"] = self._email
        try:
            resp = await self._client.get(API_URL, params=params)
        except httpx.TimeoutException:
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "timeout", "Translation timed out.") from None
        except httpx.HTTPError:
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "network", "Could not reach the translation service.") from None
        if resp.status_code == 429:
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "rate_limited", "Translation rate limit reached.")
        if resp.status_code >= 500:
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "server", f"Translation service error ({resp.status_code}).")
        try:
            body = resp.json()
        except ValueError:
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "server", "Translation service returned an invalid response.") from None
        if body.get("quotaFinished"):
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "quota", "Free daily translation quota used up (set MYMEMORY_EMAIL for more).")
        status = int(body.get("responseStatus") or resp.status_code)
        translated = (body.get("responseData") or {}).get("translatedText") or ""
        if status == 429 or "MYMEMORY WARNING" in translated.upper():
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "quota", "Free daily translation quota used up.")
        if status == 403 and "LANGPAIR" in str(body.get("responseDetails", "")).upper():
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "unsupported_language", "This language pair is not supported.")
        if status != 200 or not translated:
            fb = await self._fallback_gtx(text, source, target)
            if fb:
                return fb
            raise ProviderError("mymemory", "bad_request", f"Translation failed ({status}).")
        return html.unescape(choose_translation(text, target.split("-")[0], body)).strip()

    async def translate(self, text: str, source: str, target: str) -> str:
        text = text.strip()
        if not text or source.split("-")[0] == target.split("-")[0]:
            return text
        fixed = phrasebook.lookup(text, source, target)
        if fixed is not None:
            return fixed
        key = (text, source, target)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        parts = [await self._one(p, source, target) for p in split_for_limit(text)]
        result = " ".join(parts)
        self._cache[key] = result
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return result

    async def close(self) -> None:
        await self._client.aclose()
