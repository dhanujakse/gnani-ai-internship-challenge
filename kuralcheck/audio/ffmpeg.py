"""Thin ffmpeg wrapper. Uses the ffmpeg bundled with imageio-ffmpeg (same binary everywhere,
including Streamlit Cloud), falling back to ffmpeg on PATH. Output is bit-exact: no
encoder tags or metadata, so the same input always gives byte-identical files.
"""

import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

BITEXACT = ["-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact"]


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        path = shutil.which("ffmpeg")
        if not path:
            raise RuntimeError("ffmpeg not found: run `uv sync` (installs imageio-ffmpeg)") from None
        return path


def run_ffmpeg(*args: str | Path) -> None:
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *map(str, args)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()[:500]}")


def to_wav(src: str | Path, dst: str | Path, sample_rate: int = 16000) -> Path:
    """Any audio file -> mono 16-bit PCM WAV at sample_rate."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg("-i", src, "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", *BITEXACT, dst)
    return dst
