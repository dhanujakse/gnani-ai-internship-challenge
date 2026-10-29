"""Languages offered by the app: only those supported by all three providers.

- Gnani Prisma streaming STT: bn, en, gu, hi, kn, ml, mr, pa, ta, te (-IN)      (docs.gnani.ai/api/STT/stt-websocket)
- Gnani Timbre v2.5 TTS: same 10, voices per preferred language          (docs.gnani.ai/api/TTS/available-voices)
- MyMemory translation: ISO 639-1 codes (ta<->en tested live; the other pairs use the same API)
Tamil and English are listed first; they are the primary pair.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str  # BCP-47 as used by Gnani, e.g. ta-IN
    name: str
    native: str
    voices: tuple[str, ...]  # Timbre v2.5 voices for this language, first = default

    @property
    def iso(self) -> str:
        return self.code.split("-")[0]


LANGUAGES: tuple[Language, ...] = (
    Language("ta-IN", "Tamil", "தமிழ்", ("Trisha", "Asmita", "Brinda", "Vedika", "Noopur")),
    Language("en-IN", "English", "English", ("Kaveri", "Pranav", "Trupti", "Devika", "Shlok", "Girish")),
    Language("hi-IN", "Hindi", "हिन्दी", ("Nalini", "Deepak", "Bhavna", "Chitra", "Roopesh", "Urmila")),
    Language("te-IN", "Telugu", "తెలుగు", ("Lavanya", "Suhana", "Lehara")),
    Language("kn-IN", "Kannada", "ಕನ್ನಡ", ("Kavin", "Saanvi")),
    Language("ml-IN", "Malayalam", "മലയാളം", ("Reshma", "Riyaan")),
    Language("mr-IN", "Marathi", "मराठी", ("Ishaan",)),
    Language("bn-IN", "Bengali", "বাংলা", ("Kirra", "Dhruva")),
    Language("gu-IN", "Gujarati", "ગુજરાતી", ("Falak",)),
    Language("pa-IN", "Punjabi", "ਪੰਜਾਬੀ", ("Mehuli",)),
)
BY_CODE = {lang.code: lang for lang in LANGUAGES}
SPEED_MIN, SPEED_MAX = 0.85, 1.15  # Timbre speed range


def get_language(code: str) -> Language:
    if code not in BY_CODE:
        raise ValueError(f"Unsupported language '{code}'. Supported: {', '.join(BY_CODE)}")
    return BY_CODE[code]


def voice_for(code: str, voice: str | None) -> str:
    lang = get_language(code)
    return voice if voice in lang.voices else lang.voices[0]


def clamp_speed(speed: float | None) -> float:
    if speed is None:
        return 1.0
    return max(SPEED_MIN, min(SPEED_MAX, float(speed)))


def catalog() -> list[dict]:
    return [{"code": l.code, "name": l.name, "native": l.native, "voices": list(l.voices),
             "auto_detect": True} for l in LANGUAGES]  # fmt: skip
