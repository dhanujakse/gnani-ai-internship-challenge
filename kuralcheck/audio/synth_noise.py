"""Synthetic background noise for C3/C4 when no recorded clips are available.

- babble: 6 overlapping talkers made from dev-split Timbre clips (unintelligible crowd/cafe noise)
- fan: pink (1/f) noise with a weak mains hum and slow wobble
- traffic: brown (1/f^2) rumble with slow swells from passing vehicles

All deterministic from a seed. Clearly labelled "synthetic" in data/noise/NOTICE; real recordings
(street, kitchen, TV) can replace or join them later.
"""

import numpy as np

SR = 16000


def _normalise(x: np.ndarray, peak: float = 0.5) -> np.ndarray:
    x = x - np.mean(x)
    return (x * (peak / max(np.max(np.abs(x)), 1e-9))).astype(np.float32)


def _colored(n: int, exponent: float, rng: np.random.Generator) -> np.ndarray:
    """Noise with power spectrum ~ 1/f^exponent (0 white, 1 pink, 2 brown)."""
    spec = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    freqs[0] = freqs[1]
    spec *= 1 / freqs ** (exponent / 2)
    spec[freqs < 20] = 0  # no DC / sub-audio drift
    return np.fft.irfft(spec, n)


def _smooth_envelope(n: int, rng: np.random.Generator, points_per_s: float, depth: float) -> np.ndarray:
    k = max(2, int(n / SR * points_per_s))
    anchors = rng.uniform(1 - depth, 1, k)
    return np.interp(np.arange(n), np.linspace(0, n - 1, k), anchors)


def fan(seconds: float, rng: np.random.Generator) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    x = _colored(n, 1.0, rng)
    x = x / np.std(x)
    hum = 0.08 * (np.sin(2 * np.pi * 100 * t) + 0.5 * np.sin(2 * np.pi * 200 * t))
    return _normalise((x + hum) * _smooth_envelope(n, rng, 0.5, 0.15))


def traffic(seconds: float, rng: np.random.Generator) -> np.ndarray:
    n = int(seconds * SR)
    x = _colored(n, 2.0, rng)
    x = x / np.std(x)
    hiss = 0.3 * _colored(n, 1.0, rng) / np.std(_colored(n, 1.0, rng))
    swells = _smooth_envelope(n, rng, 0.4, 0.8) ** 2  # vehicles passing
    return _normalise((x + hiss) * swells)


def babble(clips: list[np.ndarray], seconds: float, rng: np.random.Generator, talkers: int = 6) -> np.ndarray:
    """Overlap `talkers` independent streams of randomly ordered clips."""
    if not clips:
        raise ValueError("babble needs at least one speech clip")
    n = int(seconds * SR)
    out = np.zeros(n, dtype=np.float64)
    for _ in range(talkers):
        stream: list[np.ndarray] = [np.zeros(int(rng.integers(0, SR)))]
        length = len(stream[0])
        while length < n:
            clip = clips[int(rng.integers(0, len(clips)))]
            gain = rng.uniform(0.6, 1.0)
            stream.append(clip * gain)
            gap = np.zeros(int(rng.uniform(0.05, 0.3) * SR))
            stream.append(gap)
            length += len(clip) + len(gap)
        out += np.concatenate(stream)[:n]
    return _normalise(out)
