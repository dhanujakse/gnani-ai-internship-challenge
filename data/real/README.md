# Real recordings

30 short clips of colloquial / dialect Tamil and slang, from consenting speakers (10 dev, 20 test).

## Recording
- Phone voice recorder, quiet room, phone held normally. One sentence per clip, 2–15 seconds.
- Save as WAV (8–44.1 kHz, mono). Convert other formats first, e.g.
  `uv run python -c "from kuralcheck.audio.ffmpeg import to_wav; to_wav('in.m4a', 'data/real/real01.wav')"`
- File name = row id: `real01.wav`, `real02.wav`, …
- Speakers read **scripted** lines. No real calls, no names, phone numbers, addresses or IDs in what they say.

## sentences.csv row
`real01,<exact words as spoken, Tamil script>,<accepted spellings>,colloquial,madurai,real,S01,test`

- `category`: colloquial, dialect or slang
- `dialect`: chennai, madurai, kongu, tirunelveli, thanjavur, jaffna or other
- `voice_or_speaker`: anonymous code S01, S02, … (never a name)
- Write the reference as actually spoken (colloquial spelling), and add the formal spelling and
  other common spellings in `accepted_variants`, e.g. `அவங்க=அவர்கள்|வருவாங்க=வருவார்கள்`.

## Consent (`consent.csv`)
One row per speaker: `S01,yes,2026-10-27,madurai`.
Each speaker signs this line on paper (kept offline, not in the repo):

> "I agree that my recording of these scripted sentences is published under CC BY 4.0."
