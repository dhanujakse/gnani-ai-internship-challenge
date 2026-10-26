"""Try your voice: record a sentence, hear it on a simulated noisy phone line, compare transcripts.
The recording is processed in a temp folder and deleted; it is never stored or cached."""

import streamlit as st
import ui

from kuralcheck.audio.conditions import CONDITIONS
from kuralcheck.clients.errors import ApiError
from kuralcheck.clients.prisma import PrismaClient
from kuralcheck.webapp import (
    MAX_VOICE_SECONDS,
    VOICE_RUNS_PER_SESSION,
    diff_html,
    run_voice_job,
    session_allows,
    session_count,
)

ui.page("Try your voice", "🎙️")
st.title("Try your voice")
st.markdown(
    "Say a Tamil sentence the way you normally talk. We send it to Gnani **Prisma** twice: as recorded, and "
    "through a simulated **noisy phone line** (8 kHz band, background noise, G.711 codec). Compare what it heard."
)
st.caption(f"Up to {MAX_VOICE_SECONDS} seconds. Your recording is processed in memory and deleted; nothing is stored.")

key = ui.api_key()
if not key:
    st.info("The Gnani API key is not configured on this server, so live tests are off.")
    st.stop()
if not ui.access_ok():
    st.stop()

recorded = st.audio_input("Record a sentence", sample_rate=16000)
uploaded = st.file_uploader("…or upload a short clip", type=["wav", "mp3", "m4a", "ogg", "webm", "flac"])
reference = st.text_input("What did you say? (optional, Tamil script, to score the result)")
left = VOICE_RUNS_PER_SESSION - int(st.session_state.get("voice_runs", 0))
st.caption(f"Tries left in this session: {max(left, 0)}")

source = recorded or uploaded
if st.button("Transcribe", type="primary", disabled=source is None or left <= 0):
    if not session_allows(st.session_state, "voice_runs", VOICE_RUNS_PER_SESSION):
        st.error("You have used all tries for this session.")
        st.stop()
    if not ui.daily_cap().try_spend(2):
        st.error("Today's shared API budget is used up. Please try again tomorrow.")
        st.stop()
    session_count(st.session_state, "voice_runs")
    try:
        with st.spinner("Transcribing…"):
            result = run_voice_job(
                source.getvalue(), getattr(source, "name", "voice.wav") or "voice.wav",
                PrismaClient(key, cache=None),  # never cache user recordings or their transcripts
                ui.noise_bank(), reference,
            )  # fmt: skip
    except (ApiError, ValueError, RuntimeError) as exc:
        st.error(str(exc))
        st.stop()

    phone = result["phone_condition"]
    a, b = st.columns(2)
    for col, cond, title in ((a, "C1", "As recorded"), (b, phone, CONDITIONS[phone].label)):
        col.subheader(title)
        col.audio(result["audio"][cond], format="audio/wav")
        if reference.strip():
            col.metric("Character error rate", f"{100 * result[f'{cond}_cer']:.0f}%")
            col.markdown(f"<div class='kc-diff'>{diff_html(reference, result[cond])}</div>", unsafe_allow_html=True)
        else:
            col.markdown(f"<div class='kc-diff'>{result[cond] or '(nothing recognised)'}</div>", unsafe_allow_html=True)
    if phone == "C2":
        st.caption("No noise clips on this server, so the phone version has no added noise.")
    del result  # drop audio from memory once rendered
