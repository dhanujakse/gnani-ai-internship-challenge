import hashlib
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from kuralcheck.audio.conditions import CONDITIONS, NoiseBank, build_all_conditions, load_clean
from kuralcheck.audio.noise import mix_at_snr, noise_segment, rng_for, snr_db

SR = 16000


def tone(freq: float, seconds: float = 2.0, sr: int = SR, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def speechlike(seconds: float = 2.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = sum(tone(f, seconds, amp=0.1) for f in (220, 440, 880, 1500, 2500))
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * np.arange(len(x)) / SR)
    return (x * envelope + 0.01 * rng.standard_normal(len(x))).astype(np.float32)


def band_level_db(x: np.ndarray, sr: int, freq: float) -> float:
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    band = (freqs > freq * 0.95) & (freqs < freq * 1.05)
    return 20 * np.log10(spec[band].max() / len(x) + 1e-12)


# --- noise mixing (pure functions)


@pytest.mark.parametrize("target", [15.0, 5.0, 0.0, 30.0])
def test_mix_hits_exact_snr(target: float) -> None:
    sig = speechlike()
    noise = np.random.default_rng(1).standard_normal(len(sig)).astype(np.float32)
    mix, actual, _ = mix_at_snr(sig, noise, target)
    assert actual == pytest.approx(target, abs=0.01)
    assert len(mix) == len(sig)
    # the noise actually added has the target SNR against the signal
    if np.max(np.abs(sig + (mix - sig))) <= 0.99:
        assert snr_db(sig, mix - sig) == pytest.approx(target, abs=0.05)


def test_mix_prevents_clipping_without_changing_snr() -> None:
    sig = tone(1000, amp=0.99)
    noise = np.random.default_rng(2).standard_normal(len(sig)).astype(np.float32)
    mix, actual, _ = mix_at_snr(sig, noise, 0.0)
    assert np.max(np.abs(mix)) <= 0.99
    assert actual == pytest.approx(0.0, abs=0.01)


def test_snr_db_definition() -> None:
    s = np.ones(100, dtype=np.float32)
    n = np.full(100, 0.1, dtype=np.float32)
    assert snr_db(s, n) == pytest.approx(20.0)


def test_noise_segment_is_seeded_and_loops_short_noise() -> None:
    noise = np.arange(1000, dtype=np.float32)
    a, off_a = noise_segment(noise, 2500, rng_for(42, "utt1"))
    b, off_b = noise_segment(noise, 2500, rng_for(42, "utt1"))
    c, off_c = noise_segment(noise, 2500, rng_for(42, "utt2"))
    assert len(a) == 2500 and np.array_equal(a, b) and off_a == off_b
    assert off_c != off_a or not np.array_equal(a, c)


# --- full conditions through ffmpeg


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Path]:
    src = tmp_path / "src.wav"
    sf.write(src, speechlike(3.0), SR, subtype="PCM_16")
    noise_dir = tmp_path / "noise"
    noise_dir.mkdir()
    rng = np.random.default_rng(7)
    sf.write(noise_dir / "fan.wav", (0.2 * rng.standard_normal(SR * 5)).astype(np.float32), 22050)
    sf.write(noise_dir / "street.wav", (0.2 * rng.standard_normal(SR * 2)).astype(np.float32), SR)
    return {"src": src, "noise": noise_dir, "out": tmp_path / "out"}


def _build(ws: dict[str, Path], out: Path, seed: int = 42) -> dict:
    bank = NoiseBank.load(ws["noise"])
    return build_all_conditions(ws["src"], "num01__Trisha", out, bank, seed=seed)


def test_outputs_rates_durations_and_snr(workspace) -> None:
    info = _build(workspace, workspace["out"])
    assert set(info) == set(CONDITIONS)
    for cond, row in info.items():
        data, sr = sf.read(row["path"], dtype="float32")
        assert sr == (16000 if cond == "C1" else 8000)
        assert sf.info(row["path"]).subtype == "PCM_16"
        assert len(data) / sr == pytest.approx(3.0, rel=0.01)
        target = CONDITIONS[cond].snr_db
        if target is None:
            assert row["snr_db_actual"] is None
        else:
            assert row["snr_db_actual"] == pytest.approx(target, abs=0.5)
            assert row["noise_file"] in ("fan.wav", "street.wav")


def test_same_seed_gives_byte_identical_files(workspace, tmp_path) -> None:
    a = _build(workspace, tmp_path / "a")
    b = _build(workspace, tmp_path / "b")
    for cond in CONDITIONS:
        ha = hashlib.sha256(Path(a[cond]["path"]).read_bytes()).hexdigest()
        hb = hashlib.sha256(Path(b[cond]["path"]).read_bytes()).hexdigest()
        assert ha == hb == a[cond]["sha256"]


def test_different_seed_changes_noisy_conditions_only(workspace, tmp_path) -> None:
    a = _build(workspace, tmp_path / "a", seed=42)
    b = _build(workspace, tmp_path / "b", seed=7)
    assert a["C1"]["sha256"] == b["C1"]["sha256"]
    assert a["C2"]["sha256"] == b["C2"]["sha256"]
    assert a["C4"]["sha256"] != b["C4"]["sha256"]


def test_phone_band_removes_low_and_high_frequencies(tmp_path) -> None:
    src = tmp_path / "tones.wav"
    sf.write(src, tone(100, amp=0.2) + tone(1000, amp=0.2) + tone(6000, amp=0.2), SR, subtype="PCM_16")
    out = build_all_conditions(src, "tones", tmp_path / "o", NoiseBank([]), seed=42, conditions=("C1", "C2"))
    c1, sr1 = sf.read(out["C1"]["path"], dtype="float32")
    c2, sr2 = sf.read(out["C2"]["path"], dtype="float32")
    keep = band_level_db(c2, sr2, 1000) - band_level_db(c1, sr1, 1000)
    low = band_level_db(c2, sr2, 100) - band_level_db(c1, sr1, 100)
    assert abs(keep) < 1.5  # speech band kept
    assert low < -12  # 100 Hz hum cut by the 300 Hz high-pass
    assert sr2 == 8000  # 6 kHz cannot exist at 8 kHz (Nyquist 4 kHz)


def test_noisy_condition_without_noise_files_fails_clearly(workspace) -> None:
    with pytest.raises(ValueError, match="data/noise"):
        build_all_conditions(workspace["src"], "x", workspace["out"], NoiseBank([]), seed=42)


def test_load_clean_resamples_to_16k_mono(tmp_path) -> None:
    stereo = np.stack([tone(440, sr=44100), tone(440, sr=44100)], axis=1)
    p = tmp_path / "s.wav"
    sf.write(p, stereo, 44100)
    x = load_clean(p)
    assert x.ndim == 1 and len(x) == pytest.approx(2 * SR, rel=0.01)
