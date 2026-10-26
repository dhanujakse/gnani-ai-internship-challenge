"""Mix noise into speech at an exact SNR. Pure numpy; seeded per utterance.

SNR is measured over the whole clip: 10*log10(mean(signal^2) / mean(noise^2)).
If the mix would clip, signal and noise are scaled down together, which keeps the SNR exact.
"""

import zlib

import numpy as np

PEAK = 0.99


def power(x: np.ndarray) -> float:
    return float(np.mean(np.square(x, dtype=np.float64)))


def snr_db(signal: np.ndarray, noise: np.ndarray) -> float:
    return 10.0 * np.log10(power(signal) / power(noise))


def rng_for(seed: int, key: str) -> np.random.Generator:
    """Same (seed, utterance) -> same noise, independent of processing order."""
    return np.random.default_rng([seed, zlib.crc32(key.encode("utf-8"))])


def noise_segment(noise: np.ndarray, length: int, rng: np.random.Generator) -> tuple[np.ndarray, int]:
    """A random window of `length` samples; short noise is looped. Returns (segment, offset)."""
    if len(noise) == 0:
        raise ValueError("empty noise clip")
    reps = int(np.ceil((length + len(noise)) / len(noise)))
    looped = np.tile(noise, reps)
    offset = int(rng.integers(0, len(noise)))
    return looped[offset : offset + length].astype(np.float32), offset


def mix_at_snr(
    signal: np.ndarray, noise: np.ndarray, target_snr_db: float
) -> tuple[np.ndarray, float, float]:
    """Returns (mix, actual SNR in dB, final noise gain). noise must match signal length."""
    if len(noise) != len(signal):
        raise ValueError("noise and signal lengths differ")
    if power(noise) == 0 or power(signal) == 0:
        raise ValueError("signal and noise must not be silent")
    gain = np.sqrt(power(signal) / (power(noise) * 10 ** (target_snr_db / 10)))
    s = signal.astype(np.float64)
    n = noise.astype(np.float64) * gain
    mix = s + n
    peak = float(np.max(np.abs(mix)))
    if peak > PEAK:
        scale = PEAK / peak
        s, n, mix = s * scale, n * scale, mix * scale
        gain *= scale
    return mix.astype(np.float32), snr_db(s, n), float(gain)
