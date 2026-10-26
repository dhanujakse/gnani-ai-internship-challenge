# KuralCheck-ta v1 — Datasheet

A small Tamil speech test set for stress-testing speech recognition on colloquial and dialect Tamil,
numbers and code-mixed English, under clean, telephone-band and noisy phone conditions.
Built for the Gnani.ai Great Indian AI Internship Challenge (2026).

## Contents

<!-- stats:start -->
- **Scripted (Timbre):** 60 sentences (20 dev / 40 test), 180 utterances with audio; categories: code_mixed 15, everyday 20, names_places 10, numbers 15; voices: Asmita, Brinda, Trisha
- **Audio:** 720 files across 4 conditions; 7.6 minutes of speech per condition
- **C3 measured SNR:** 15.00–15.00 dB (n=180)
- **C4 measured SNR:** 5.00–5.00 dB (n=180)
- **Noise clips used:** babble_synthetic.wav, fan_synthetic.wav, traffic_synthetic.wav
<!-- stats:end -->

## Composition

- **Scripted (synthetic):** standard-Tamil sentences written by the team, spoken by Gnani Timbre
  (text-to-speech) in three voices. Categories: numbers / money / time (including two-digit numbers),
  names and places, code-mixed English words, everyday sentences. Numbers are written as words.
- **Real recordings:** colloquial and dialect Tamil and slang, read from scripted lines by consenting
  speakers on their own phones. Each speaker has an anonymous code (S01, S02, …).
- **Splits:** `dev` (used to tune the fix layer) and `test` (used only for reported numbers).

## Conditions

| Condition | How it is made |
|---|---|
| C1 Clean | Original audio, 16 kHz mono 16-bit WAV |
| C2 Phone band | 300–3400 Hz band-pass, resampled to 8 kHz |
| C3 Phone + light noise | Noise mixed at 15 dB SNR (measured), then C2, then G.711 μ-law encode/decode |
| C4 Phone + heavy noise | Noise mixed at 5 dB SNR (measured), then the same phone chain |

Noise is mixed in Python with a fixed seed (42) per utterance; the exact SNR, noise clip and offset of
every file are in `conditions_manifest.csv`. The same seed reproduces byte-identical files.

## Files in the zip

- `sentences.csv`: id, reference text, accepted spellings (`|` separated; `formal=colloquial` word swaps
  or full alternative sentences), category, dialect, source, voice or speaker code, split
- `conditions_manifest.csv`: one row per audio file with sample rate, duration, SNR, noise clip, sha256
- `audio/C1 … C4/<utterance>.wav`: Timbre utterances are named `<id>__<voice>.wav`, real ones `<id>.wav`
- `speakers.csv`: anonymous speaker code and dialect
- `NOISE_NOTICE.txt`: source and licence of every noise clip
- `LICENSE.txt`: CC BY 4.0

## Consent and privacy

- Every real speaker agreed in writing: *"I agree that my recording of these scripted sentences is
  published under CC BY 4.0."* Signed forms are kept offline by the team.
- Speakers read scripted lines only. There are no real phone calls, names of speakers, phone numbers,
  addresses or ID numbers in the audio, text or metadata.
- Names of people and places that appear in sentences are common examples, not personal data.

## Intended use and limits

- **Use for:** checking how a speech recogniser handles colloquial Tamil, numbers and phone-line audio;
  comparing settings or models with the same normalisation.
- **Small set:** a few speakers and dialects. Report bootstrap confidence intervals and n, and do not
  treat differences inside the intervals as real.
- **Synthetic audio is easier** than real speech (clean, standard pronunciation, same vendor as Prisma),
  so synthetic and real results must be reported separately.
- **Not for training** speech models or identifying speakers.

## Licence and citation

Audio, transcripts and metadata: **CC BY 4.0**. Code (github repository): MIT.

> KuralCheck-ta v1: a Tamil colloquial and phone-line speech test set (2026). CC BY 4.0.
