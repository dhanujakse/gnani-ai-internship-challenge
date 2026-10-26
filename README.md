# KuralCheck — Tamil speech stress-test kit

**How well does Indian AI understand the Tamil people actually speak, on a bad phone line?**

KuralCheck measures how Gnani Prisma (speech-to-text) handles colloquial and dialect Tamil on clean,
8 kHz and noisy phone audio, adds a fix layer, and publishes a scorecard, a Streamlit app and a
downloadable test set. Test audio for scripted sentences is generated with Gnani Timbre (text-to-speech).

> Work in progress for the Gnani.ai Great Indian AI Internship Challenge. No results yet;
> every number here will be generated from `results/*.json`.

## Setup

```bash
cp .env.example .env     # add GNANI_API_KEY
uv sync
uv run pytest -q
```

ffmpeg must be on your PATH for building audio conditions.

## Method (summary)

- **Conditions:** C1 clean 16 kHz · C2 phone band 8 kHz · C3 phone + 15 dB SNR noise · C4 phone + 5 dB SNR noise
- **Prisma settings:** F0 verbatim · F1 ITN · F2 ITN + bias words · F3 F2 + lexicon fixes
- **Metrics:** CER (primary), WER, number accuracy, bootstrap 95% CI, always with n
- Fix layer tuned on the dev split only; headline numbers from the test split only.

Older BhashaBridge code is kept in `legacy/` for reference and is not part of this project.
