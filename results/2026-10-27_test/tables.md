# Results: test split

- Date: 2026-10-27 · commit `2096557`
- Models: stt=gnani-prisma (stt/v3), stt_version=Prisma v2.5, tts=timbre-v2.5
- Utterances: 120 · records: 1920 · failed: 0
- Prisma calls: 1440 unique (0 new, 1440 cached)
- Latency per call: p50 280.1 ms · p95 1054.2 ms (n=1440)
- Bias words: 9 · lexicon rules: 1

Cells: metric in % with bootstrap 95% CI (1000 resamples, seed 42). Lower CER/WER is better.
Small team-made test set: read intervals, not just point values.

## Synthetic (Timbre, standard Tamil) · gnani-prisma (stt/v3)

**CER %** (primary)

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 120 | 0.9 (0.5–1.5) | 3.2 (1.9–4.9) | 3.2 (1.9–4.9) | 2.2 (1.1–3.4) |
| C2 Phone band 8 kHz | 120 | 1.1 (0.6–1.7) | 3.4 (1.9–5.0) | 3.4 (1.9–5.0) | 2.3 (1.3–3.5) |
| C3 Phone + light noise (15 dB) | 120 | 1.3 (0.7–1.9) | 3.6 (2.1–5.1) | 3.6 (2.1–5.1) | 2.5 (1.4–3.7) |
| C4 Phone + heavy noise (5 dB) | 120 | 3.0 (2.1–4.1) | 5.5 (3.8–7.1) | 5.4 (3.8–7.0) | 4.3 (2.9–5.7) |

**WER %**

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 120 | 4.7 (2.8–7.0) | 7.8 (5.3–10.5) | 7.8 (5.3–10.5) | 7.0 (4.6–9.5) |
| C2 Phone band 8 kHz | 120 | 5.4 (3.4–7.9) | 8.3 (5.6–11.0) | 8.3 (5.6–11.0) | 7.5 (5.1–10.0) |
| C3 Phone + light noise (15 dB) | 120 | 6.1 (3.7–8.6) | 8.9 (6.1–11.9) | 8.9 (6.1–11.9) | 8.2 (5.6–10.9) |
| C4 Phone + heavy noise (5 dB) | 120 | 10.6 (7.7–13.7) | 13.2 (10.0–16.6) | 12.9 (9.7–16.3) | 12.0 (8.9–15.1) |

**Number accuracy %** (higher is better; utterances containing numbers)

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 30 | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) |
| C2 Phone band 8 kHz | 30 | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) |
| C3 Phone + light noise (15 dB) | 30 | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) |
| C4 Phone + heavy noise (5 dB) | 30 | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) |

**CER % by category · C1 Clean 16 kHz**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 30 | 1.0 (0.1–2.4) | 10.3 (5.6–15.6) | 10.3 (5.6–15.6) | 6.2 (2.7–10.2) |
| Names and places | 21 | 0.7 (0.2–1.4) | 0.7 (0.2–1.4) | 0.7 (0.2–1.4) | 0.7 (0.2–1.4) |
| Code-mixed English | 30 | 1.4 (0.6–2.3) | 1.4 (0.6–2.3) | 1.4 (0.6–2.3) | 1.4 (0.6–2.3) |
| Everyday | 39 | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) |

**CER % by category · C2 Phone band 8 kHz**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 30 | 1.3 (0.3–2.7) | 10.4 (5.7–15.8) | 10.4 (5.7–15.8) | 6.3 (2.9–10.3) |
| Names and places | 21 | 0.7 (0.2–1.4) | 0.7 (0.2–1.4) | 0.7 (0.2–1.4) | 0.7 (0.2–1.4) |
| Code-mixed English | 30 | 1.7 (0.6–3.1) | 1.7 (0.6–3.1) | 1.7 (0.6–3.1) | 1.7 (0.6–3.1) |
| Everyday | 39 | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) |

**CER % by category · C3 Phone + light noise (15 dB)**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 30 | 1.0 (0.3–2.0) | 10.1 (5.4–15.5) | 10.1 (5.4–15.5) | 6.0 (2.7–9.9) |
| Names and places | 21 | 1.1 (0.3–2.1) | 1.1 (0.3–2.1) | 1.1 (0.3–2.1) | 1.1 (0.3–2.1) |
| Code-mixed English | 30 | 2.6 (1.1–4.5) | 2.6 (1.1–4.5) | 2.6 (1.1–4.5) | 2.6 (1.1–4.5) |
| Everyday | 39 | 0.4 (0.0–1.0) | 0.4 (0.0–1.0) | 0.4 (0.0–1.0) | 0.4 (0.0–1.0) |

**CER % by category · C4 Phone + heavy noise (5 dB)**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 30 | 1.6 (0.5–2.6) | 10.9 (6.1–16.2) | 10.9 (6.1–16.2) | 6.6 (3.2–10.5) |
| Names and places | 21 | 1.7 (0.8–2.8) | 1.7 (0.8–2.8) | 1.7 (0.8–2.8) | 1.7 (0.8–2.8) |
| Code-mixed English | 30 | 5.1 (3.0–7.5) | 5.1 (3.0–7.5) | 5.1 (3.0–7.5) | 5.1 (3.0–7.5) |
| Everyday | 39 | 3.8 (1.3–6.6) | 3.8 (1.3–6.6) | 3.5 (1.1–6.3) | 3.5 (1.1–6.3) |
