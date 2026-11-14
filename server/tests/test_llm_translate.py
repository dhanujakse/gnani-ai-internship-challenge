"""LLM translator (providers/llm_translate.py): uses the model, falls back on any failure, pauses when out of credit."""

import asyncio
import json

import httpx

from sarvagyan_server.config import Settings
from sarvagyan_server.main import make_translator
from sarvagyan_server.providers.llm_translate import LlmTranslator, clean
from sarvagyan_server.providers.mymemory import MyMemoryTranslator


class Fallback:
    name = "fallback"

    def __init__(self) -> None:
        self.calls = 0

    async def translate(self, text: str, source: str, target: str) -> str:
        self.calls += 1
        return "FALLBACK"


def make(responses: list, fallback=None) -> tuple[LlmTranslator, list[dict], Fallback]:
    """responses: (status, content) per request, the last one repeats."""
    seen: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append({"auth": req.headers.get("authorization"), "body": json.loads(req.content)})
        status, content = responses[min(len(seen), len(responses)) - 1]
        if status != 200:
            return httpx.Response(status, json={"error": "nope"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    fb = fallback or Fallback()
    tr = LlmTranslator("https://llm.example/v1/", "k-123", "some/model", fb,
                       client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))  # fmt: skip
    return tr, seen, fb


def run(coro):
    return asyncio.run(coro)


def test_uses_the_model_with_key_model_and_languages() -> None:
    tr, seen, fb = make([(200, "நீங்க இப்போ எங்கே இருக்கீங்க?")])
    out = run(tr.translate("Where are you right now?", "en-IN", "ta-IN"))
    assert out == "நீங்க இப்போ எங்கே இருக்கீங்க?" and fb.calls == 0
    assert seen[0]["auth"] == "Bearer k-123" and seen[0]["body"]["model"] == "some/model"
    system = seen[0]["body"]["messages"][0]["content"]
    assert "from English to Tamil" in system
    assert seen[0]["body"]["messages"][1]["content"] == "Where are you right now?"


def test_model_answers_are_cached() -> None:
    tr, seen, _ = make([(200, "நான் வீட்டுக்கு போறேன்")])
    for _ in range(3):
        run(tr.translate("I am going home now", "en-IN", "ta-IN"))
    assert len(seen) == 1


def test_out_of_credit_falls_back_and_pauses_the_model() -> None:
    tr, seen, fb = make([(402, "")])
    assert run(tr.translate("Where are you right now?", "en-IN", "ta-IN")) == "FALLBACK"
    assert tr.last_error == "quota" and not tr.available
    assert run(tr.translate("Call me back later please", "en-IN", "ta-IN")) == "FALLBACK"
    assert len(seen) == 1 and fb.calls == 2  # paused: the second sentence never waited for the model


def test_server_error_falls_back_without_pausing() -> None:
    tr, seen, fb = make([(503, ""), (200, "I am at home")])
    assert run(tr.translate("நான் வீட்டில் இருக்கேன்", "ta-IN", "en-IN")) == "FALLBACK"
    assert tr.available
    assert run(tr.translate("நான் வீட்டில் இருக்கேன்", "ta-IN", "en-IN")) == "I am at home"  # fallback wasn't cached


def test_wrong_script_or_rambling_answer_is_rejected() -> None:
    tr, _, fb = make([(200, "Where are you?")])  # English back when Tamil was asked for
    assert run(tr.translate("Where are you?", "en-IN", "ta-IN")) == "FALLBACK"
    tr, _, fb = make([(200, "வணக்கம் " * 80)])
    assert run(tr.translate("Coming soon", "en-IN", "ta-IN")) == "FALLBACK"


def test_network_failure_falls_back() -> None:
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    fb = Fallback()
    tr = LlmTranslator("https://llm.example/v1", "k", "m", fb, client=httpx.AsyncClient(transport=httpx.MockTransport(boom)))
    assert run(tr.translate("Where are you right now?", "en-IN", "ta-IN")) == "FALLBACK"
    assert tr.last_error == "network"


def test_same_language_and_phrasebook_skip_the_model() -> None:
    tr, seen, _ = make([(200, "x")])
    assert run(tr.translate("hello there", "en-IN", "en-US")) == "hello there"
    run(tr.translate("hello", "en-IN", "ta-IN"))  # a phrasebook phrase
    assert seen == []


def test_clean_strips_labels_quotes_and_reasoning() -> None:
    assert clean('<think>hmm</think>\n"வணக்கம்"') == "வணக்கம்"
    assert clean("Translation: I am coming") == "I am coming"


def test_make_translator_needs_a_key() -> None:
    assert isinstance(make_translator(Settings(_env_file=None, TRANSLATE_LLM_KEY="")), MyMemoryTranslator)
    tr = make_translator(Settings(_env_file=None, HF_TOKEN="hf_x"))
    assert isinstance(tr, LlmTranslator) and isinstance(tr.fallback, MyMemoryTranslator)
    assert tr.model == "google/gemma-3-27b-it"
