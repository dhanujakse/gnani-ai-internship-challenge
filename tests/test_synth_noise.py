import numpy as np
import pytest

from kuralcheck.audio.synth_noise import SR, babble, fan, traffic


def spectrum_slope(x: np.ndarray) -> float:
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    band = (f > 100) & (f < 4000)
    return float(np.polyfit(np.log10(f[band]), np.log10(spec[band] + 1e-12), 1)[0])


def test_fan_is_pink_and_traffic_is_brown() -> None:
    rng = np.random.default_rng(0)
    assert -1.5 < spectrum_slope(fan(5, rng)) < -0.5
    assert spectrum_slope(traffic(5, rng)) < -1.5


def test_lengths_peaks_and_determinism() -> None:
    a = fan(2, np.random.default_rng(1))
    b = fan(2, np.random.default_rng(1))
    assert len(a) == 2 * SR and np.array_equal(a, b)
    assert np.max(np.abs(a)) == pytest.approx(0.5, abs=1e-3)


def test_babble_overlaps_talkers() -> None:
    rng = np.random.default_rng(2)
    clip = np.sin(2 * np.pi * 300 * np.arange(SR) / SR).astype(np.float32)
    x = babble([clip], 3, rng, talkers=6)
    assert len(x) == 3 * SR and np.max(np.abs(x)) == pytest.approx(0.5, abs=1e-3)
    with pytest.raises(ValueError):
        babble([], 1, rng)
