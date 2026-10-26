"""KuralCheck results dashboard: reads results/ only, never runs the benchmark."""

import altair as alt
import pandas as pd
import streamlit as st
import ui

from kuralcheck.audio.conditions import CONDITIONS
from kuralcheck.report.tables import CATEGORY_LABELS, SOURCE_LABELS
from kuralcheck.runner import group_metrics
from kuralcheck.webapp import diff_html, filter_records

ui.page("Results")
st.title("KuralCheck · குரல்செக்")
st.markdown(
    "**How well does Indian AI understand the Tamil people actually speak, on a bad phone line?** "
    "We ran Gnani Prisma on colloquial, dialect and scripted Tamil under four phone-line conditions, "
    "added a fix layer, and measured character error rate (CER) with 95% confidence intervals."
)

all_runs = ui.runs()
prisma_runs = [r for r in all_runs if not r.is_whisper]
if not prisma_runs:
    st.info(
        "No benchmark results yet. They appear here after the team runs "
        "`scripts/run_benchmark.py`; every number on this page comes from `results/`."
    )
    st.markdown(
        "- **Conditions:** C1 clean 16 kHz · C2 phone band 8 kHz · C3 phone + 15 dB noise · C4 phone + 5 dB noise\n"
        "- **Settings:** F0 verbatim · F1 ITN · F2 ITN + bias words · F3 F2 + lexicon fixes\n"
        "- Try the **Test your sentences** and **Try your voice** pages in the sidebar."
    )
    st.stop()

# --- choose the run (default: latest test split)
names = [r.name for r in prisma_runs]
default = max((i for i, r in enumerate(prisma_runs) if r.split == "test"), default=len(prisma_runs) - 1)
run = prisma_runs[st.sidebar.selectbox("Benchmark run", range(len(names)), index=default, format_func=lambda i: names[i])]
whisper_run = next((r for r in reversed(all_runs) if r.is_whisper and r.split == run.split), None)
meta = run.summary["run"]
if run.split != "test":
    st.warning("This is a **dev-split** run, used to tune the fix layer. Headline numbers use the test split.")

records = ui.load_records(str(run.path), (run.path / "raw.jsonl").stat().st_mtime)
if whisper_run and st.sidebar.checkbox("Include Whisper small (open model)", value=True):
    records = records + ui.load_records(str(whisper_run.path), (whisper_run.path / "raw.jsonl").stat().st_mtime)

# --- scorecard + run facts
left, right = st.columns([3, 2])
with left:
    card = run.path / "scorecard.png"
    if card.exists():
        st.image(str(card), width="stretch")
with right:
    lat = meta.get("latency_ms") or {}
    calls = meta.get("prisma_calls") or {}
    st.subheader("This run")
    c1, c2 = st.columns(2)
    c1.metric("Split", meta.get("split", "–"))
    c2.metric("Utterances", meta.get("n_utterances", "–"))
    c1.metric("Latency p50", f"{lat['p50'] / 1000:.2f} s" if lat.get("p50") else "–")
    c2.metric("Latency p95", f"{lat['p95'] / 1000:.2f} s" if lat.get("p95") else "–")
    st.markdown(
        f"<div class='kc-muted'>Prisma calls: {calls.get('unique', '–')} · failed records: {meta.get('n_failures', 0)}<br>"
        f"Models: {', '.join(f'{k}: {v}' for k, v in (meta.get('models') or {}).items())}<br>"
        f"Date {meta.get('created_at', '')[:10]} · commit {meta.get('git_commit')}<br>"
        f"Bias words {meta.get('bias_words', {}).get('n', 0)} · lexicon rules {meta.get('lexicon', {}).get('n_rules', 0)}</div>",
        unsafe_allow_html=True,
    )
    st.download_button("Download raw results (JSONL)", (run.path / "raw.jsonl").read_bytes(), f"{run.name}_raw.jsonl")

# --- filters (one row)
st.divider()
f1, f2, f3, f4 = st.columns(4)
present = lambda key: sorted({r[key] for r in records})  # noqa: E731
sources = f1.multiselect("Source", present("source"), format_func=lambda s: SOURCE_LABELS.get(s, s))
conds = f2.multiselect("Condition", present("condition"), format_func=lambda c: f"{c} {CONDITIONS[c].label}")
cats = f3.multiselect("Category", present("category"), format_func=lambda c: CATEGORY_LABELS.get(c, c))
sets = f4.multiselect("Setting", present("setting"), format_func=lambda s: ui.SETTING_NAMES.get(s, s))
filtered = filter_records(records, source=sources, condition=conds, category=cats, setting=sets)
ok = [r for r in filtered if r.get("error") is None]
if not ok:
    st.warning("No scored records match these filters.")
    st.stop()


@st.cache_data(show_spinner="Computing confidence intervals…")
def metrics_table(rows: tuple) -> pd.DataFrame:
    recs = [dict(r) for r in rows]
    out = []
    for g in group_metrics(recs, ("source", "condition", "setting")):
        if not g["n"]:
            continue
        cer, wer, num = g["cer"], g["wer"], g.get("number_accuracy")
        out.append({
            "Source": g["source"], "Condition": g["condition"], "Setting": g["setting"], "n": g["n"],
            "CER %": round(100 * cer["value"], 1), "CER low": round(100 * cer["low"], 1), "CER high": round(100 * cer["high"], 1),
            "WER %": round(100 * wer["value"], 1),
            "Numbers %": round(100 * num["value"], 1) if num else None,
            "Failures": g["failures"],
        })  # fmt: skip
    return pd.DataFrame(out)


slim = tuple(
    tuple(sorted({k: r[k] for k in ("source", "condition", "setting", "category", "error", "ref_used", "hyp_norm",
                                    "char_edits", "char_ref", "word_edits", "word_ref", "num_matched", "num_ref",
                                    "utt_id", "model")}.items()))
    for r in filtered
)  # fmt: skip
table = metrics_table(slim)

st.subheader("Character error rate by condition")
st.caption("Bars: CER % (lower is better). Whiskers: bootstrap 95% CI over utterances. Hover for n.")
for source in table["Source"].unique():
    df = table[table["Source"] == source].copy()
    df["Setting name"] = df["Setting"].map(ui.SETTING_NAMES)
    domain = [s for s in ui.SETTING_COLORS if s in set(df["Setting"])]
    base = alt.Chart(df).encode(
        x=alt.X("Condition:N", sort=list(CONDITIONS), title=None),
        xOffset=alt.XOffset("Setting:N", sort=domain),
    )
    bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="#fcfcfb", strokeWidth=2).encode(
        y=alt.Y("CER %:Q", title="CER %"),
        color=alt.Color("Setting:N", scale=alt.Scale(domain=domain, range=[ui.SETTING_COLORS[s] for s in domain]),
                        legend=alt.Legend(orient="top", title=None, labelExpr="datum.label")),
        tooltip=["Condition", "Setting name", "n", "CER %", "CER low", "CER high", "WER %", "Numbers %"],
    )  # fmt: skip
    whiskers = base.mark_rule(color="#52514e").encode(y="CER low:Q", y2="CER high:Q")
    st.markdown(f"**{SOURCE_LABELS.get(source, source)}**")
    st.altair_chart((bars + whiskers).properties(height=320), width="stretch")

with st.expander("Table view (all numbers, with n)", expanded=False):
    st.dataframe(table, hide_index=True, width="stretch")

# --- example errors
st.subheader("Example errors")
st.caption("Reference vs what was heard, after normalisation. Struck red = missed or wrong, green = inserted.")
k = st.slider("How many", 5, 50, 10)
worst = sorted(ok, key=lambda r: (r["char_edits"] / r["char_ref"]) if r["char_ref"] else 0, reverse=True)[:k]
for r in worst:
    cer = r["char_edits"] / r["char_ref"] if r["char_ref"] else 0
    st.markdown(
        f"<div class='kc-muted'>{r['utt_id']} · {r['condition']} · {ui.SETTING_NAMES.get(r['setting'], r['setting'])} · CER {100 * cer:.0f}%</div>"
        f"<div class='kc-diff'>{diff_html(r['ref_used'], r['hyp_norm'])}</div>",
        unsafe_allow_html=True,
    )
st.caption("Small team-made test set: read the intervals, not only the point values. Method and data: see the Download page.")
