"""The four audio conditions (see the project notes "Definitions"):

C1 clean 16 kHz
C2 band-pass 300-3400 Hz + 8 kHz
C3 noise at 15 dB SNR, then the C2 chain, then G.711 mu-law encode/decode
C4 noise at 5 dB SNR, then the same phone chain

Noise is mixed in Python at 16 kHz (exact, logged SNR); ffmpeg does the filters,
resampling and codec. All outputs are 16-bit PCM WAV.
"""

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from kuralcheck.audio.ffmpeg import BITEXACT, run_ffmpeg, to_wav
from kuralcheck.audio.noise import mix_at_snr, noise_segment, rng_for

CLEAN_SR = 16000
PHONE_SR = 8000
PHONE_FILTER = "highpass=f=300,lowpass=f=3400"


@dataclass(frozen=True)
class ConditionSpec:
    name: str
    label: str
    snr_db: float | None
    phone: bool
    mulaw: bool


CONDITIONS: dict[str, ConditionSpec] = {
    "C1": ConditionSpec("C1", "Clean 16 kHz", None, phone=False, mulaw=False),
    "C2": ConditionSpec("C2", "Phone band 8 kHz", None, phone=True, mulaw=False),
    "C3": ConditionSpec("C3", "Phone + light noise (15 dB)", 15.0, phone=True, mulaw=True),
    "C4": ConditionSpec("C4", "Phone + heavy noise (5 dB)", 5.0, phone=True, mulaw=True),
}


def load_clean(path: str | Path) -> np.ndarray:
    """Any audio file -> mono float32 at 16 kHz (via ffmpeg, so every input is treated alike)."""
    with tempfile.TemporaryDirectory() as tmp:
        wav = to_wav(path, Path(tmp) / "clean.wav", CLEAN_SR)
        data, _ = sf.read(wav, dtype="float32")
    return data


@dataclass
class NoiseBank:
    clips: list[tuple[str, np.ndarray]]  # (file name, 16 kHz mono samples), sorted by name

    @classmethod
    def load(cls, noise_dir: str | Path) -> "NoiseBank":
        files = sorted(
            p for p in Path(noise_dir).glob("*") if p.suffix.lower() in (".wav", ".flac", ".mp3", ".ogg", ".m4a")
        )
        return cls([(p.name, load_clean(p)) for p in files])

    def pick(self, length: int, seed: int, key: str) -> tuple[str, np.ndarray, int]:
        if not self.clips:
            raise ValueError("no noise clips: add WAV files to data/noise/ (see data/noise/NOTICE)")
        rng = rng_for(seed, key)
        name, samples = self.clips[int(rng.integers(0, len(self.clips)))]
        segment, offset = noise_segment(samples, length, rng)
        return name, segment, offset


def _write_pcm16(path: Path, data: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.clip(data, -1.0, 1.0), sr, subtype="PCM_16")


def _phone_chain(src: Path, dst: Path, mulaw: bool, tmp: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not mulaw:
        run_ffmpeg("-i", src, "-af", PHONE_FILTER, "-ar", PHONE_SR, "-ac", "1", "-c:a", "pcm_s16le", *BITEXACT, dst)
        return
    coded = tmp / "mulaw.wav"
    run_ffmpeg("-i", src, "-af", PHONE_FILTER, "-ar", PHONE_SR, "-ac", "1", "-c:a", "pcm_mulaw", *BITEXACT, coded)
    run_ffmpeg("-i", coded, "-c:a", "pcm_s16le", *BITEXACT, dst)


def build_condition(
    clean: np.ndarray, utt_id: str, spec: ConditionSpec, out_path: Path, noise: NoiseBank, seed: int
) -> dict:
    """Write one condition file; returns its manifest row."""
    row: dict = {
        "utt_id": utt_id,
        "condition": spec.name,
        "path": out_path.as_posix(),
        "snr_db_target": spec.snr_db,
        "snr_db_actual": None,
        "noise_file": None,
        "noise_offset_s": None,
        "seed": seed,
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        audio = clean
        if spec.snr_db is not None:
            name, segment, offset = noise.pick(len(clean), seed, f"{utt_id}|{spec.name}")
            audio, actual, _ = mix_at_snr(clean, segment, spec.snr_db)
            row.update(
                snr_db_actual=round(actual, 3), noise_file=name, noise_offset_s=round(offset / CLEAN_SR, 3)
            )
        if not spec.phone:
            _write_pcm16(out_path, audio, CLEAN_SR)
        else:
            src = tmp / "in.wav"
            _write_pcm16(src, audio, CLEAN_SR)
            _phone_chain(src, out_path, spec.mulaw, tmp)

    info = sf.info(out_path)
    row.update(
        sample_rate=info.samplerate,
        duration_s=round(info.frames / info.samplerate, 3),
        sha256=hashlib.sha256(out_path.read_bytes()).hexdigest(),
    )
    return row


def build_all_conditions(
    source_audio: str | Path,
    utt_id: str,
    out_root: Path,
    noise: NoiseBank,
    seed: int,
    conditions: tuple[str, ...] = tuple(CONDITIONS),
) -> dict[str, dict]:
    """out_root/C1/<utt_id>.wav ... out_root/C4/<utt_id>.wav"""
    clean = load_clean(source_audio)
    return {
        c: build_condition(clean, utt_id, CONDITIONS[c], Path(out_root) / c / f"{utt_id}.wav", noise, seed)
        for c in conditions
    }
