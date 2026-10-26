"""Generate clean 16 kHz WAVs for Timbre sentences: one file per (sentence, voice)."""

import io
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

from kuralcheck.audio.ffmpeg import to_wav
from kuralcheck.clients.timbre import TimbreClient, TimbreSettings
from kuralcheck.data import Utterance


@dataclass(frozen=True)
class SynthJob:
    utt: Utterance
    settings: TimbreSettings

    @property
    def text(self) -> str:
        return self.utt.sentence.text


def plan(utts: list[Utterance], model: str) -> list[SynthJob]:
    """Timbre utterances whose WAV is not on disk yet."""
    return [
        SynthJob(u, TimbreSettings(voice=u.voice_or_speaker, model=model))  # type: ignore[arg-type]
        for u in utts
        if u.sentence.source == "timbre" and not u.source_audio.exists()
    ]


def save_wav(audio: bytes, path: Path, sample_rate: int = 16000) -> None:
    """Store as 16 kHz mono 16-bit; converts if Timbre returned something else."""
    path.parent.mkdir(parents=True, exist_ok=True)
    info = sf.info(io.BytesIO(audio))
    if info.samplerate == sample_rate and info.channels == 1 and info.subtype == "PCM_16":
        path.write_bytes(audio)
        return
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        raw.write_bytes(audio)
        to_wav(raw, path, sample_rate)


def run(
    jobs: list[SynthJob],
    client: TimbreClient,
    workers: int = 4,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[int, list[tuple[str, str]]]:
    """Returns (new API calls made, [(utt_id, error)])."""
    new_calls = 0
    errors: list[tuple[str, str]] = []

    def one(job: SynthJob) -> bool:
        res = client.synthesize(job.text, job.settings)
        save_wav(res.audio, job.utt.source_audio)
        return not res.cached

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, j): j for j in jobs}
        for i, fut in enumerate(as_completed(futures), start=1):
            job = futures[fut]
            try:
                new_calls += fut.result()
            except Exception as exc:  # keep going; report at the end
                errors.append((job.utt.utt_id, str(exc)))
            if progress:
                progress(i, len(jobs))
    return new_calls, errors
