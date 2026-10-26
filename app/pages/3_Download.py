"""Download the KuralCheck Tamil test set (CC BY 4.0) and read its datasheet."""

import streamlit as st
import ui

from kuralcheck.report.runs import latest
from kuralcheck.webapp import get_secret

ui.page("Download", "📦")
st.title("Download the test set")
st.markdown(
    "**KuralCheck-ta v1**: scripted standard Tamil (spoken by Gnani Timbre, 3 voices) and consented real "
    "recordings of colloquial and dialect Tamil, each in four conditions (clean, 8 kHz phone band, phone + "
    "15 dB noise, phone + 5 dB noise), with reference transcripts, accepted spellings and metadata. "
    "Licence: **CC BY 4.0**."
)

zip_path = ui.ROOT / "dist" / "kuralcheck-ta-v1.zip"
url = get_secret("DATASET_URL")
if zip_path.exists():
    st.download_button("Download kuralcheck-ta-v1.zip", zip_path.read_bytes(), zip_path.name, type="primary")
elif url:
    st.link_button("Download kuralcheck-ta-v1.zip", url, type="primary")
else:
    st.info("The dataset zip is published with the final release. Check back soon.")

run = latest("test")
if run:
    st.download_button(
        "Benchmark results (summary.json)",
        (run.path / "summary.json").read_bytes(),
        f"kuralcheck_{run.name}_summary.json",
    )

st.divider()
datasheet = ui.ROOT / "DATASHEET.md"
if datasheet.exists():
    st.markdown(datasheet.read_text(encoding="utf-8"))
st.caption("Code: MIT. Dataset: CC BY 4.0. Fonts: Noto Sans / Noto Sans Tamil (SIL OFL).")
