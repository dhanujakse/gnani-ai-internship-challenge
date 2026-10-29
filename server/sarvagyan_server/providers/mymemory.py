"""MyMemory translation API (mymemory.translated.net/doc/spec.php).

GET https://api.mymemory.translated.net/get?q=<text>&langpair=ta|en[&de=<email>]
- q is limited to 500 bytes (UTF-8), so longer text is split on sentence/word boundaries
- free quota: 5,000 chars/day anonymous, 50,000 with a contact email (`de`)
Response (observed live): {"responseData": {"translatedText": ...}, "responseStatus": 200, "quotaFinished": false}
A small in-memory LRU cache avoids paying twice for repeated phrases ("hello", "okay"...).
"""

import html
import re
from collections import OrderedDict

import httpx

from sarvagyan_server.providers.base import ProviderError

API_URL = "https://api.mymemory.translated.net/get"
MAX_Q_BYTES = 480  # stay under the 500-byte limit
CACHE_SIZE = 512
_SENTENCE = re.compile(r"(?<=[.!?।])\s+")


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

    async def _one(self, text: str, source: str, target: str) -> str:
        params = {"q": text, "langpair": f"{source.split('-')[0]}|{target.split('-')[0]}"}
        if self._email:
            params["de"] = self._email
        try:
            resp = await self._client.get(API_URL, params=params)
        except httpx.TimeoutException:
            raise ProviderError("mymemory", "timeout", "Translation timed out.") from None
        except httpx.HTTPError:
            raise ProviderError("mymemory", "network", "Could not reach the translation service.") from None
        if resp.status_code == 429:
            raise ProviderError("mymemory", "rate_limited", "Translation rate limit reached.")
        if resp.status_code >= 500:
            raise ProviderError("mymemory", "server", f"Translation service error ({resp.status_code}).")
        try:
            body = resp.json()
        except ValueError:
            raise ProviderError("mymemory", "server", "Translation service returned an invalid response.") from None
        if body.get("quotaFinished"):
            raise ProviderError("mymemory", "quota", "Free daily translation quota used up (set MYMEMORY_EMAIL for more).")
        status = int(body.get("responseStatus") or resp.status_code)
        translated = (body.get("responseData") or {}).get("translatedText") or ""
        if status == 429 or "MYMEMORY WARNING" in translated.upper():
            raise ProviderError("mymemory", "quota", "Free daily translation quota used up.")
        if status == 403 and "LANGPAIR" in str(body.get("responseDetails", "")).upper():
            raise ProviderError("mymemory", "unsupported_language", "This language pair is not supported.")
        if status != 200 or not translated:
            raise ProviderError("mymemory", "bad_request", f"Translation failed ({status}).")
        return html.unescape(translated).strip()

    async def translate(self, text: str, source: str, target: str) -> str:
        text = text.strip()
        if not text or source.split("-")[0] == target.split("-")[0]:
            return text
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
