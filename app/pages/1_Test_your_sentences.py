"""Test your own sentences: Timbre speaks them, KuralCheck degrades the audio, Prisma transcribes."""

import streamlit as st
import ui

from kuralcheck.audio.conditions import CONDITIONS
from kuralcheck.clients.errors import ApiError
from kuralcheck.clients.prisma import PrismaClient
from kuralcheck.clients.timbre import TAMIL_VOICES_V25, TimbreClient
from kuralcheck.webapp import (
    MAX_SENTENCES,
    SENTENCE_RUNS_PER_SESSION,
    diff_html,
    get_secret,
    parse_sentences,
    run_sentence_job,
    session_allows,
    session_count,
)

ui.page("Test your sentences", "📝")
st.title("Test your sentences")
st.markdown(
    f"Paste up to **{MAX_SENTENCES} Tamil sentences** (one per line). Gnani **Timbre** speaks them, we make a clean "
    "and a noisy phone-line version, and Gnani **Prisma** transcribes both, raw (F0) and with the KuralCheck fix "
    "layer (F3). Write numbers as words."
)

key = ui.api_key()
if not key:
    st.info("The Gnani API key is not configured on this server, so live tests are off. The Results page still works.")
    st.stop()
if not ui.access_ok():
    st.stop()

text = st.text_area("Sentences", height=180, placeholder="நாளைக்கு காலையில பத்து மணிக்கு கடைக்கு வாங்க\nஎன் போன் சார்ஜ் ஆகல")
voice = st.selectbox("Timbre voice", TAMIL_VOICES_V25, index=1)
left = SENTENCE_RUNS_PER_SESSION - int(st.session_state.get("sentence_runs", 0))
st.caption(f"Runs left in this session: {max(left, 0)}")

if st.button("Run test", type="primary", disabled=left <= 0):
    sentences, problems = parse_sentences(text)
    if not sentences:
        problems = problems or ["Enter at least one sentence."]
    if problems:
        for p in problems:
            st.error(p)
        st.stop()
    if not session_allows(st.session_state, "sentence_runs", SENTENCE_RUNS_PER_SESSION):
        st.error("You have used all test runs for this session.")
        st.stop()
    if not ui.daily_cap().try_spend(5 * len(sentences)):  # 1 Timbre + 4 Prisma per sentence, at most
        st.error("Today's shared API budget is used up. Please try again tomorrow.")
        st.stop()
    session_count(st.session_state, "sentence_runs")
    bias, lexicon = ui.fix_layer()
    cache = ui.shared_cache()
    model = get_secret("TTS_MODEL", "timbre-v2.5") or "timbre-v2.5"
    try:
        with st.spinner(f"Speaking and transcribing {len(sentences)} sentence(s)…"):
            report = run_sentence_job(
                sentences, voice, model, TimbreClient(key, cache), PrismaClient(key, cache),
                ui.noise_bank(), bias, lexicon,
            )  # fmt: skip
        st.session_state["sentence_report"] = report
    except (ApiError, ValueError, RuntimeError) as exc:
        st.error(f"Something went wrong: {exc}")

report = st.session_state.get("sentence_report")
if report:
    clean, noisy = report["conditions"]
    o = report["overall_cer"]
    st.subheader(f"Mini report · n = {report['n']} sentence(s)")
    if noisy == "C2":
        st.caption("No noise clips on this server, so the noisy column uses the plain phone band (C2).")
    m1, m2, m3 = st.columns(3)
    m1.metric(f"CER · {CONDITIONS[clean].label} · F0", f"{100 * o[f'{clean}_F0']:.1f}%")
    m2.metric(f"CER · {CONDITIONS[noisy].label} · F0", f"{100 * o[f'{noisy}_F0']:.1f}%")
    m3.metric(f"CER · {CONDITIONS[noisy].label} · F3", f"{100 * o[f'{noisy}_F3']:.1f}%",
              delta=f"{100 * (o[f'{noisy}_F3'] - o[f'{noisy}_F0']):+.1f} pts", delta_color="inverse")  # fmt: skip
    st.caption("CER = character error rate (lower is better). Tiny samples are noisy; this is a quick check, not a benchmark.")
    for i, row in enumerate(report["rows"], start=1):
        with st.expander(f"{i}. {row['sentence']}", expanded=i == 1):
            a, b = st.columns(2)
            for col, cond in ((a, clean), (b, noisy)):
                col.markdown(f"**{cond} {CONDITIONS[cond].label}**")
                col.audio(row["audio"][cond], format="audio/wav")
                for setting in ("F0", "F3"):
                    hyp = row[f"{cond}_{setting}"]
                    col.markdown(
                        f"<div class='kc-muted'>{setting} · CER {100 * row[f'{cond}_{setting}_cer']:.0f}%</div>"
                        f"<div class='kc-diff'>{diff_html(row['sentence'], hyp)}</div>",
                        unsafe_allow_html=True,
                    )
