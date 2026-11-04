"""Fixed translations for very short, very common call phrases.

MyMemory is a crowd-sourced translation memory. For short inputs like "hello" or "Hi, how are you?" it often
returns an unrelated human entry (probed 30 Oct 2026: "hello" -> "Create a coherent unified sentence",
"Hi, how are you?" -> "my child after a long time"). These phrases are the most frequent in a call, so they are
answered from this table instead: correct every time, instant, and no quota used.
"""

import re

_STRIP = re.compile(r"[\s.,!?।…\"]+")
_APOSTROPHES = re.compile(r"['’]")

_EN_TA = {
    "hi": "ஹாய்",
    "hello": "ஹலோ",
    "hey": "ஹேய்",
    "hi there": "ஹாய்",
    "hello there": "ஹலோ",
    "good morning": "காலை வணக்கம்",
    "good afternoon": "மதிய வணக்கம்",
    "good evening": "மாலை வணக்கம்",
    "good night": "இனிய இரவு",
    "how are you": "எப்படி இருக்கீங்க?",
    "hi how are you": "ஹாய், எப்படி இருக்கீங்க?",
    "hello how are you": "ஹலோ, எப்படி இருக்கீங்க?",
    "i am fine": "நான் நல்லா இருக்கேன்",
    "i'm fine": "நான் நல்லா இருக்கேன்",
    "im fine": "நான் நல்லா இருக்கேன்",
    "i am good": "நான் நல்லா இருக்கேன்",
    "i'm good": "நான் நல்லா இருக்கேன்",
    "ok": "சரி",
    "okay": "சரி",
    "yes": "ஆமாம்",
    "yeah": "ஆமா",
    "no": "இல்லை",
    "thank you": "நன்றி",
    "thanks": "நன்றி",
    "thank you so much": "ரொம்ப நன்றி",
    "sorry": "மன்னிக்கவும்",
    "please": "தயவுசெய்து",
    "bye": "பை",
    "goodbye": "போயிட்டு வரேன்",
    "bye bye": "பை பை",
    "see you": "அப்புறம் பார்க்கலாம்",
    "what": "என்ன?",
    "can you hear me": "நான் பேசுறது கேக்குதா?",
    "i can hear you": "எனக்கு கேக்குது",
}

_TA_EN = {
    "ஹாய்": "Hi",
    "ஹலோ": "Hello",
    "ஹேய்": "Hey",
    "வணக்கம்": "Hello",
    "காலை வணக்கம்": "Good morning",
    "மாலை வணக்கம்": "Good evening",
    "எப்படி இருக்கீங்க": "How are you?",
    "எப்படி இருக்கிறீர்கள்": "How are you?",
    "நீங்க எப்படி இருக்கீங்க": "How are you?",
    "நீங்கள் எப்படி இருக்கிறீர்கள்": "How are you?",
    "ஹாய் எப்படி இருக்கீங்க": "Hi, how are you?",
    "ஹலோ எப்படி இருக்கீங்க": "Hello, how are you?",
    "நல்லா இருக்கேன்": "I'm fine",
    "நான் நல்லா இருக்கேன்": "I'm fine",
    "சரி": "Okay",
    "ஓகே": "Okay",
    "ஆமா": "Yes",
    "ஆமாம்": "Yes",
    "இல்லை": "No",
    "இல்ல": "No",
    "நன்றி": "Thank you",
    "ரொம்ப நன்றி": "Thank you so much",
    "மன்னிக்கவும்": "Sorry",
    "சாரி": "Sorry",
    "பை": "Bye",
    "பை பை": "Bye bye",
    "என்ன": "What?",
    "கேக்குதா": "Can you hear me?",
}



def _norm(text: str) -> str:
    return _STRIP.sub(" ", _APOSTROPHES.sub("", text.lower())).strip()


_TABLES = {pair: {_norm(k): v for k, v in table.items()} for pair, table in {("en", "ta"): _EN_TA, ("ta", "en"): _TA_EN}.items()}


def lookup(text: str, source: str, target: str) -> str | None:
    """The fixed translation for a common short phrase, or None. Languages are ISO codes or BCP-47 (ta-IN)."""
    table = _TABLES.get((source.split("-")[0], target.split("-")[0]))
    if not table:
        return None
    return table.get(_norm(text))
