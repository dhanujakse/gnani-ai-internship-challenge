import io
from collections.abc import Iterator

import numpy as np
import pytest
import respx
import soundfile as sf

from kuralcheck.cache import Cache

BASE = "https://api.vachana.ai"


def make_wav(seconds: float = 1.0, sr: int = 16000) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, np.zeros(int(seconds * sr), dtype=np.float32), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@pytest.fixture
def wav() -> bytes:
    return make_wav()


@pytest.fixture
def cache(tmp_path) -> Iterator[Cache]:
    c = Cache(tmp_path / "cache.sqlite")
    yield c
    c.close()


@pytest.fixture
def mock_api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture
def no_sleep() -> list[float]:
    """Collects requested sleeps instead of sleeping."""
    return []
