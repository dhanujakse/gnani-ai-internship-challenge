# Results: test split

- Date: 2026-10-27 · commit `e86f502`
- Models: stt=whisper-small, runtime=faster-whisper (CTranslate2, int8, CPU), language=ta
- Utterances: 120 · records: 480 · failed: 0
- Prisma calls: 480 unique (480 new, 0 cached)
- Latency per call: p50 6028.1 ms · p95 6979.6 ms (n=480)
- Bias words: None · lexicon rules: None

Cells: metric in % with bootstrap 95% CI (1000 resamples, seed 42). Lower CER/WER is better.
Small team-made test set: read intervals, not just point values.

## Synthetic (Timbre, standard Tamil) · whisper-small

**CER %** (primary)

| Condition | n | W0 |
|---|---|---|
| C1 Clean 16 kHz | 120 | 10.6 (9.0–12.3) |
| C2 Phone band 8 kHz | 120 | 11.1 (9.5–12.6) |
| C3 Phone + light noise (15 dB) | 120 | 13.8 (12.0–15.6) |
| C4 Phone + heavy noise (5 dB) | 120 | 27.4 (24.4–30.8) |

**WER %**

| Condition | n | W0 |
|---|---|---|
| C1 Clean 16 kHz | 120 | 40.6 (35.9–45.2) |
| C2 Phone band 8 kHz | 120 | 41.5 (36.8–46.0) |
| C3 Phone + light noise (15 dB) | 120 | 45.8 (41.1–50.5) |
| C4 Phone + heavy noise (5 dB) | 120 | 66.3 (61.4–70.9) |

**Number accuracy %** (higher is better; utterances containing numbers)

| Condition | n | W0 |
|---|---|---|
| C1 Clean 16 kHz | 30 | 61.5 (50.0–73.0) |
| C2 Phone band 8 kHz | 30 | 61.5 (48.6–74.4) |
| C3 Phone + light noise (15 dB) | 30 | 66.7 (52.8–79.5) |
| C4 Phone + heavy noise (5 dB) | 30 | 56.4 (39.0–71.8) |

**CER % by category · C1 Clean 16 kHz**

| Category | n | W0 |
|---|---|---|
| Numbers, money, time | 30 | 10.4 (7.2–14.9) |
| Names and places | 21 | 10.0 (7.8–12.2) |
| Code-mixed English | 30 | 16.2 (13.6–19.0) |
| Everyday | 39 | 6.1 (4.0–8.8) |

**CER % by category · C2 Phone band 8 kHz**

| Category | n | W0 |
|---|---|---|
| Numbers, money, time | 30 | 11.4 (7.7–15.8) |
| Names and places | 21 | 11.1 (9.2–12.9) |
| Code-mixed English | 30 | 15.6 (13.0–18.4) |
| Everyday | 39 | 6.7 (4.4–9.6) |

**CER % by category · C3 Phone + light noise (15 dB)**

| Category | n | W0 |
|---|---|---|
| Numbers, money, time | 30 | 13.9 (9.3–19.5) |
| Names and places | 21 | 12.2 (10.0–14.4) |
| Code-mixed English | 30 | 20.2 (17.5–23.3) |
| Everyday | 39 | 9.1 (6.6–12.4) |

**CER % by category · C4 Phone + heavy noise (5 dB)**

| Category | n | W0 |
|---|---|---|
| Numbers, money, time | 30 | 28.3 (22.7–34.9) |
| Names and places | 21 | 20.6 (15.4–26.5) |
| Code-mixed English | 30 | 34.2 (28.5–41.2) |
| Everyday | 39 | 25.4 (20.4–31.4) |
