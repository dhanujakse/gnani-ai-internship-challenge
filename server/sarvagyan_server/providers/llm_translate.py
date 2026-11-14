"""Translation by a large language model through any OpenAI-compatible chat API (Hugging Face Inference Providers by
default; Groq, Google Gemini's OpenAI endpoint, OpenRouter and others work the same way).

POST {base_url}/chat/completions with Authorization: Bearer <key>, a short system prompt and the sentence.
LLMs translate spoken, colloquial Indian-language sentences far better than MyMemory's crowd-sourced memory, and,
unlike the free Google endpoint, they don't refuse a cloud server's shared IP address.

Every failure falls through to the `fallback` translator (MyMemory, which itself tries Google first), so a call
never loses its subtitles. Out of credit (402), a bad key (401/403) or rate limiting (429) pauses this provider for a
while, so later sentences don't wait for a request that will fail. Answers in the wrong script or of implausible
length are rejected the same way MyMemory's are.
"""

import logging
import re
import time
from collections import OrderedDict

import httpx

from sarvagyan_server.providers import phrasebook
from sarvagyan_server.providers.base import ProviderError, Translator
from sarvagyan_server.providers.mymemory import in_script

log = logging.getLogger(__name__)

CACHE_SIZE = 2048
PAUSE_S = {"quota": 600.0, "auth": 600.0, "rate_limited": 30.0}

NAMES = {
    "en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu", "kn": "Kannada", "ml": "Malayalam",
    "bn": "Bengali", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi", "or": "Odia",
}
_THINK = re.compile(r"<think>.*?</think>", re.S)


def system_prompt(source: str, target: str) -> str:
    src, tgt = NAMES.get(source, source), NAMES.get(target, target)
    return (
        f"You are the interpreter on a live phone call. Translate what the caller said from {src} to {tgt}. "
        f"The text comes from speech recognition: it can be informal, colloquial or slightly misrecognised, so "
        f"translate the intended meaning the way a native {tgt} speaker would naturally say it on a call. "
        f"Keep names, numbers and English words people commonly use as they are. "
        f"Reply with only the {tgt} translation written in {tgt} script: no quotes, notes, or explanations."
    )


def clean(answer: str) -> str:
    """Strip reasoning blocks, wrapping quotes and a 'Translation:' label some models add."""
    text = _THINK.sub("", answer).strip()
    text = re.sub(r"^(translation|மொழிபெயர்ப்பு)\s*[:：]\s*", "", text, flags=re.I).strip()
    if len(text) >= 2 and text[0] in "\"'“‘«" and text[-1] in "\"'”’»":
        text = text[1:-1].strip()
    return text


def acceptable(source_text: str, answer: str, target: str) -> bool:
    if not answer or not in_script(answer, target):
        return False
    s, a = len(source_text), len(answer)
    return a <= 4 * s + 40 and a * 6 + 6 >= s


class LlmTranslator:
    name = "llm"

    def __init__(self, base_url: str, api_key: str, model: str, fallback: Translator,
                 client: httpx.AsyncClient | None = None, timeout_s: float = 6.0) -> None:  # fmt: skip
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self.model = model
        self.fallback = fallback
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()
        self._paused_until = 0.0
        self.last_error: str | None = None  # code of the latest failure, for diagnostics

    @property
    def available(self) -> bool:
        return time.monotonic() >= self._paused_until

    async def _llm(self, text: str, source: str, target: str) -> str:
        """One request to the model; raises ProviderError (never returns an unusable answer)."""
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt(source, target)}, {"role": "user", "content": text}],
            "temperature": 0,
            "max_tokens": max(64, 4 * len(text)),
        }
        try:
            resp = await self._client.post(self._url, json=body, headers={"Authorization": f"Bearer {self._key}"})
        except httpx.TimeoutException:
            raise ProviderError("llm", "timeout", "Translation timed out.") from None
        except httpx.HTTPError:
            raise ProviderError("llm", "network", "Could not reach the translation model.") from None
        code = resp.status_code
        if code == 402:
            raise ProviderError("llm", "quota", "The translation model's credit is used up.")
        if code in (401, 403):
            raise ProviderError("llm", "auth", "The translation model's key was refused.")
        if code == 429:
            raise ProviderError("llm", "rate_limited", "Translation model rate limit reached.")
        if code >= 500:
            raise ProviderError("llm", "server", f"Translation model error ({code}).")
        if code != 200:
            raise ProviderError("llm", "bad_request", f"Translation model rejected the request ({code}).")
        try:
            answer = clean(resp.json()["choices"][0]["message"]["content"] or "")
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("llm", "server", "Translation model returned an invalid response.") from None
        if not acceptable(text, answer, target):
            raise ProviderError("llm", "bad_request", "Translation model gave an unusable answer.")
        return answer

    async def _one(self, text: str, source: str, target: str) -> str:
        """Uncached: the model first, then the fallback. Diagnostics calls this to test the real providers."""
        return (await self._translate(text, source, target))[0]

    async def _translate(self, text: str, source: str, target: str) -> tuple[str, bool]:
        """(translation, True when the model produced it)."""
        src, tgt = source.split("-")[0], target.split("-")[0]
        if self.available:
            t0 = time.monotonic()
            try:
                answer = await self._llm(text, src, tgt)
                self.last_error = None
                return answer, True
            except ProviderError as exc:
                self.last_error = exc.code
                if exc.code in PAUSE_S:
                    self._paused_until = time.monotonic() + PAUSE_S[exc.code]
                log.warning("llm translation failed: code=%s ms=%d, using fallback", exc.code,
                            int((time.monotonic() - t0) * 1000))  # fmt: skip
        # the fallback's own translate: its phrasebook and cache still apply
        return await self.fallback.translate(text, source, target), False

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
        result, from_model = await self._translate(text, source, target)
        if from_model:  # fallback answers are cached by the fallback itself
            self._cache[key] = result
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return result

    async def close(self) -> None:
        await self._client.aclose()
        close = getattr(self.fallback, "close", None)
        if close:
            await close()
