# Results: dev split

- Date: 2026-10-26 · commit `ce30694`
- Models: stt=gnani-prisma (stt/v3), stt_version=Prisma v2.5, tts=timbre-v2.5
- Utterances: 60 · records: 960 · failed: 0
- Prisma calls: 720 unique (0 new, 720 cached)
- Latency per call: p50 283.6 ms · p95 1607.8 ms (n=720)
- Bias words: 9 · lexicon rules: 1

Cells: metric in % with bootstrap 95% CI (1000 resamples, seed 42). Lower CER/WER is better.
Small team-made test set: read intervals, not just point values.

## Synthetic (Timbre, standard Tamil) · gnani-prisma (stt/v3)

**CER %** (primary)

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 60 | 1.3 (0.6–2.0) | 5.3 (2.8–8.4) | 4.8 (2.2–7.8) | 2.2 (0.4–4.4) |
| C2 Phone band 8 kHz | 60 | 1.1 (0.5–1.8) | 5.1 (2.6–8.2) | 4.4 (1.9–7.5) | 1.9 (0.1–4.2) |
| C3 Phone + light noise (15 dB) | 60 | 1.1 (0.5–1.7) | 5.1 (2.5–8.2) | 4.9 (2.3–8.0) | 2.3 (0.5–4.5) |
| C4 Phone + heavy noise (5 dB) | 60 | 2.2 (1.3–3.2) | 6.0 (3.4–9.3) | 5.3 (2.8–8.5) | 2.7 (0.9–4.8) |

**WER %**

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 60 | 7.1 (4.2–10.3) | 11.4 (7.5–15.7) | 8.6 (4.8–12.8) | 3.4 (1.2–5.8) |
| C2 Phone band 8 kHz | 60 | 5.9 (3.4–8.6) | 10.5 (6.6–14.7) | 7.7 (3.7–12.1) | 2.5 (0.6–4.4) |
| C3 Phone + light noise (15 dB) | 60 | 6.5 (3.6–9.6) | 11.1 (7.0–15.6) | 9.0 (5.2–13.2) | 3.4 (1.3–5.8) |
| C4 Phone + heavy noise (5 dB) | 60 | 10.2 (6.5–14.3) | 13.5 (8.9–18.0) | 10.5 (6.4–14.6) | 4.9 (2.2–7.7) |

**Number accuracy %** (higher is better; utterances containing numbers)

| Condition | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| C1 Clean 16 kHz | 15 | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) |
| C2 Phone band 8 kHz | 15 | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) |
| C3 Phone + light noise (15 dB) | 15 | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) |
| C4 Phone + heavy noise (5 dB) | 15 | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) | 100.0 (100.0–100.0) |

**CER % by category · C1 Clean 16 kHz**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 15 | 1.0 (0.1–2.3) | 18.4 (8.8–28.8) | 18.4 (8.8–28.8) | 7.6 (0.0–16.1) |
| Names and places | 9 | 3.8 (0.0–7.0) | 3.8 (0.0–7.0) | 0.0 (0.0–0.0) | 0.0 (0.0–0.0) |
| Code-mixed English | 15 | 1.2 (0.4–2.0) | 1.2 (0.4–2.0) | 1.4 (0.0–3.9) | 1.2 (0.0–3.4) |
| Everyday | 21 | 0.4 (0.0–0.8) | 0.4 (0.0–0.8) | 0.4 (0.0–0.8) | 0.4 (0.0–0.8) |

**CER % by category · C2 Phone band 8 kHz**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 15 | 0.8 (0.0–2.2) | 18.4 (8.8–28.8) | 18.4 (8.8–28.8) | 7.6 (0.0–16.1) |
| Names and places | 9 | 3.1 (0.0–6.0) | 3.1 (0.0–6.0) | 0.0 (0.0–0.0) | 0.0 (0.0–0.0) |
| Code-mixed English | 15 | 1.2 (0.5–1.8) | 1.2 (0.5–1.8) | 0.4 (0.0–1.2) | 0.1 (0.0–0.5) |
| Everyday | 21 | 0.3 (0.0–0.6) | 0.3 (0.0–0.6) | 0.3 (0.0–0.6) | 0.3 (0.0–0.6) |

**CER % by category · C3 Phone + light noise (15 dB)**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 15 | 0.8 (0.0–2.2) | 18.4 (8.8–28.8) | 18.4 (8.8–28.8) | 7.6 (0.0–16.1) |
| Names and places | 9 | 3.1 (0.0–6.0) | 3.1 (0.0–6.0) | 0.0 (0.0–0.0) | 0.0 (0.0–0.0) |
| Code-mixed English | 15 | 0.9 (0.4–1.4) | 0.9 (0.4–1.4) | 1.9 (0.1–4.4) | 1.4 (0.0–4.0) |
| Everyday | 21 | 0.4 (0.0–0.8) | 0.4 (0.0–0.8) | 0.4 (0.0–0.8) | 0.4 (0.0–0.8) |

**CER % by category · C4 Phone + heavy noise (5 dB)**

| Category | n | F0 Baseline (verbatim) | F1 ITN (format=transcribe) | F2 ITN + bias words | F3 Full fix (F2 + lexicon) |
|---|---|---|---|---|---|
| Numbers, money, time | 15 | 1.7 (0.4–3.2) | 18.4 (8.8–28.8) | 18.4 (8.8–28.8) | 7.6 (0.0–16.1) |
| Names and places | 9 | 3.8 (0.5–6.5) | 3.8 (0.5–6.5) | 0.8 (0.0–2.5) | 0.8 (0.0–2.5) |
| Code-mixed English | 15 | 2.9 (0.9–5.5) | 2.9 (0.9–5.5) | 2.0 (0.3–4.3) | 1.6 (0.0–3.7) |
| Everyday | 21 | 1.2 (0.3–2.4) | 1.2 (0.3–2.4) | 1.2 (0.3–2.4) | 1.2 (0.3–2.4) |
