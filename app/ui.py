"""Shared setup for the Streamlit pages: import path, page style, cached resources, limits."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from kuralcheck.audio.conditions import NoiseBank  # noqa: E402
from kuralcheck.cache import Cache  # noqa: E402
from kuralcheck.data import NOISE_DIR  # noqa: E402
from kuralcheck.fixlayer.bias import load_bias_words  # noqa: E402
from kuralcheck.fixlayer.lexicon import Lexicon, load_lexicon  # noqa: E402
from kuralcheck.report.runs import Run, list_runs  # noqa: E402
from kuralcheck.webapp import DEFAULT_DAILY_CALL_CAP, DailyCap, get_secret  # noqa: E402

SETTING_COLORS = {"F0": "#2a78d6", "F1": "#eda100", "F2": "#6250d6", "F3": "#eb6834", "W0": "#1baf7a"}
SETTING_NAMES = {
    "F0": "F0 Baseline",
    "F1": "F1 ITN",
    "F2": "F2 ITN + bias words",
    "F3": "F3 Full fix",
    "W0": "Whisper small",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Tamil:wght@400;600&family=Noto+Sans:wght@400;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame { font-family: 'Noto Sans', 'Noto Sans Tamil', sans-serif; }
.kc-diff { font-size: 1.05rem; line-height: 1.7; }
.kc-muted { color: #52514e; font-size: 0.9rem; }
</style>
"""


def page(title: str, icon: str = "🗣️") -> None:
    st.set_page_config(page_title=f"{title} · KuralCheck", page_icon=icon, layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)


def api_key() -> str:
    return get_secret("GNANI_API_KEY")


def access_ok(container=st) -> bool:
    """Optional access code (secret ACCESS_CODE) protecting the paid-call pages."""
    code = get_secret("ACCESS_CODE")
    if not code:
        return True
    if st.session_state.get("access_ok"):
        return True
    entered = container.text_input("Access code", type="password", help="Ask the KuralCheck team for the demo code.")
    if entered and entered == code:
        st.session_state["access_ok"] = True
        return True
    if entered:
        container.error("Wrong access code.")
    return False


@st.cache_resource
def daily_cap() -> DailyCap:
    try:
        limit = int(get_secret("DAILY_CALL_CAP", str(DEFAULT_DAILY_CALL_CAP)) or DEFAULT_DAILY_CALL_CAP)
    except ValueError:
        limit = DEFAULT_DAILY_CALL_CAP
    return DailyCap(limit=limit)


@st.cache_resource
def noise_bank() -> NoiseBank:
    return NoiseBank.load(NOISE_DIR)


@st.cache_resource
def fix_layer() -> tuple[tuple[str, ...], Lexicon]:
    return load_bias_words(), load_lexicon()


@st.cache_resource
def shared_cache() -> Cache:
    """Cache for scripted-sentence jobs only (never for user recordings)."""
    return Cache(ROOT / "cache" / "app.sqlite")


def runs() -> list[Run]:
    return list_runs()


@st.cache_data(show_spinner=False)
def load_records(run_path: str, mtime: float) -> list[dict]:
    return Run(Path(run_path), {}).records()


def throttle():
    """Shared pacing for all paid calls from the app (Gnani returns 429 when calls come too fast)."""
    from kuralcheck.throttle import shared_throttle

    try:
        rate = float(get_secret("GNANI_CALLS_PER_SECOND", "1") or 1)
    except ValueError:
        rate = 1.0
    return shared_throttle(rate)
