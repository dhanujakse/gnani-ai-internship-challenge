# Results: test split

- Date: 2026-10-26 · commit `7d4768a`
- Models: stt=gnani-prisma (stt/v3), stt_version=Prisma v2.5, tts=timbre-v2.5
- Utterances: 120 · records: 1920 · failed: 19
- Prisma calls: 1426 unique (1426 new, 0 cached)
- Latency per call: p50 279.9 ms · p95 1052.2 ms (n=1426)
- Bias words: 9 · lexicon rules: 1

Cells: metric in % with bootstrap 95% CI (1000 resamples, seed 42). Lower CER/WER is better.
Small team-made test set: read intervals, not just point values.

## Synthetic (Timbre, standard Tamil) · gnani-prisma (stt/v3)

**CER %** (primary)

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 119 | 0.9 (0.5–1.4) | 3.3 (1.9–4.9) | 3.3 (1.9–4.9) | 2.2 (1.2–3.4) |
| C2 Phone band 8 kHz | 118–119 | 1.1 (0.6–1.7) | 3.4 (2.0–5.2) | 3.4 (2.0–5.2) | 2.4 (1.3–3.5) |
| C3 Phone + light noise (15 dB) | 118–119 | 1.2 (0.7–1.8) | 3.5 (2.1–5.2) | 3.4 (2.0–5.1) | 2.5 (1.5–3.7) |
| C4 Phone + heavy noise (5 dB) | 119 | 3.0 (2.0–4.1) | 5.5 (3.8–7.2) | 5.4 (3.8–7.1) | 4.3 (3.0–5.7) |

**WER %**

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 119 | 4.8 (2.8–6.9) | 7.8 (5.3–10.5) | 7.8 (5.3–10.5) | 7.0 (4.7–9.5) |
| C2 Phone band 8 kHz | 118–119 | 5.5 (3.3–7.7) | 8.3 (5.8–11.2) | 8.3 (5.8–11.2) | 7.6 (5.0–10.0) |
| C3 Phone + light noise (15 dB) | 118–119 | 5.8 (3.6–8.3) | 8.7 (5.9–11.6) | 8.5 (6.0–11.5) | 8.0 (5.4–10.8) |
| C4 Phone + heavy noise (5 dB) | 119 | 10.4 (7.5–13.6) | 13.0 (9.6–16.6) | 12.6 (9.4–16.1) | 11.7 (8.8–14.8) |

**Number accuracy %** (higher is better; utterances containing numbers)

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 30 | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) |
| C2 Phone band 8 kHz | 30 | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) |
| C3 Phone + light noise (15 dB) | 29–30 | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) |
| C4 Phone + heavy noise (5 dB) | 30 | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) | 97.4 (91.4–100.0) |

**CER % by category · C1 Clean 16 kHz**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 30 | 1.0 (0.1–2.4) | 10.3 (5.6–15.6) | 10.3 (5.6–15.6) | 6.2 (2.7–10.2) |
| Names and places | 20 | 0.7 (0.1–1.5) | 0.7 (0.1–1.5) | 0.7 (0.1–1.5) | 0.7 (0.1–1.5) |
| Code-mixed English | 30 | 1.4 (0.6–2.3) | 1.4 (0.6–2.3) | 1.4 (0.6–2.3) | 1.4 (0.6–2.3) |
| Everyday | 39 | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) |

**CER % by category · C2 Phone band 8 kHz**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 30 | 1.3 (0.3–2.7) | 10.4 (5.7–15.8) | 10.4 (5.7–15.8) | 6.3 (2.9–10.3) |
| Names and places | 19–20 | 0.8 (0.1–1.5) | 0.7 (0.1–1.5) | 0.7 (0.1–1.5) | 0.7 (0.1–1.5) |
| Code-mixed English | 30 | 1.7 (0.6–3.1) | 1.7 (0.6–3.1) | 1.7 (0.6–3.1) | 1.7 (0.6–3.1) |
| Everyday | 39 | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) | 0.6 (0.1–1.2) |

**CER % by category · C3 Phone + light noise (15 dB)**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 29–30 | 1.0 (0.3–2.0) | 10.1 (5.4–15.5) | 9.7 (4.9–15.5) | 6.1 (2.9–10.2) |
| Names and places | 20 | 0.8 (0.1–1.7) | 0.8 (0.1–1.7) | 0.8 (0.1–1.7) | 0.8 (0.1–1.7) |
| Code-mixed English | 30 | 2.6 (1.1–4.5) | 2.6 (1.1–4.5) | 2.6 (1.1–4.5) | 2.6 (1.1–4.5) |
| Everyday | 39 | 0.4 (0.0–1.0) | 0.4 (0.0–1.0) | 0.4 (0.0–1.0) | 0.4 (0.0–1.0) |

**CER % by category · C4 Phone + heavy noise (5 dB)**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 30 | 1.6 (0.5–2.6) | 10.9 (6.1–16.2) | 10.9 (6.1–16.2) | 6.6 (3.2–10.5) |
| Names and places | 20 | 1.5 (0.6–2.6) | 1.5 (0.6–2.6) | 1.5 (0.6–2.6) | 1.5 (0.6–2.6) |
| Code-mixed English | 30 | 5.1 (3.0–7.5) | 5.1 (3.0–7.5) | 5.1 (3.0–7.5) | 5.1 (3.0–7.5) |
| Everyday | 39 | 3.8 (1.3–6.6) | 3.8 (1.3–6.6) | 3.5 (1.1–6.3) | 3.5 (1.1–6.3) |
