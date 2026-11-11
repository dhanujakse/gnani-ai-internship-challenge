#!/usr/bin/env python3
"""
Build processed avatar assets (512x512 main + 128x128 thumb WebP) and avatars.json config
from the project's top-level Avatar/ folder without modifying originals.

Re-runnable: adding or removing images in Avatar/ and re-running updates assets/avatars/
and avatars.json cleanly.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "avatars"
CONFIG_PATH = ASSETS_DIR / "avatars.json"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAIN_SIZE = 512
THUMB_SIZE = 128
MAX_MAIN_BYTES = 100 * 1024  # 100 KB target


def find_avatar_dir(root: Path) -> Path:
    for entry in root.iterdir():
        if entry.is_dir() and entry.name.lower() == "avatar":
            return entry
    raise FileNotFoundError(f"Could not find an 'avatar' folder (case-insensitive) inside {root}")


def crop_square_top_biased(im: Image.Image, filename: str) -> tuple[Image.Image, str | None]:
    w, h = im.size
    if w == h:
        return im, None
    ratio = max(w / h, h / w)
    warning = None
    if ratio > 1.45:
        warning = f"REVIEW NEEDED ({filename}): aspect ratio {w}x{h} is tall/wide ({ratio:.2f}); verify head/face stays in square crop."
    side = min(w, h)
    # Center horizontally; bias vertically toward the top (10% from top margin when taller)
    left = (w - side) // 2
    top = int((h - side) * 0.10) if h > w else 0
    return im.crop((left, top, left + side, top + side)), warning


def encode_webp_under_limit(im: Image.Image, max_bytes: int | None = None) -> bytes:
    for quality in (88, 82, 76, 70, 62, 54, 46):
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=quality, method=6)
        data = buf.getvalue()
        if max_bytes is None or len(data) <= max_bytes:
            return data
    return data


def main() -> int:
    try:
        src_dir = find_avatar_dir(REPO_ROOT)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    files = sorted(
        (p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS),
        key=lambda p: p.name.lower(),
    )
    if not files:
        print(f"ERROR: No image files found in {src_dir}", file=sys.stderr)
        return 1

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in ASSETS_DIR.glob("avatar-*.webp"):
        stale.unlink()

    config: list[dict[str, str]] = []
    warnings: list[str] = []

    print(f"Source folder: {src_dir}")
    print(f"Output folder: {ASSETS_DIR}\n")
    print(f"{'ID':<10} {'Original File':<55} {'Before':>18} {'Main (512)':>14} {'Thumb (128)':>14}")
    print("-" * 118)

    for idx, src_path in enumerate(files, start=1):
        avatar_id = f"avatar-{idx:02d}"
        main_name = f"{avatar_id}.webp"
        thumb_name = f"{avatar_id}-thumb.webp"

        orig_bytes = src_path.stat().st_size
        with Image.open(src_path) as raw:
            im = ImageOps.exif_transpose(raw).convert("RGBA")
            orig_w, orig_h = im.size
            if orig_w < MAIN_SIZE or orig_h < MAIN_SIZE:
                warnings.append(
                    f"SMALL IMAGE ({src_path.name}): {orig_w}x{orig_h} < {MAIN_SIZE}px; will NOT upscale."
                )

            sq, crop_warn = crop_square_top_biased(im, src_path.name)
            if crop_warn:
                warnings.append(crop_warn)

            target_main = min(MAIN_SIZE, sq.width)
            main_im = sq if sq.width == target_main else sq.resize((target_main, target_main), Image.Resampling.LANCZOS)
            target_thumb = min(THUMB_SIZE, sq.width)
            thumb_im = sq if sq.width == target_thumb else sq.resize((target_thumb, target_thumb), Image.Resampling.LANCZOS)

            main_data = encode_webp_under_limit(main_im, MAX_MAIN_BYTES)
            thumb_data = encode_webp_under_limit(thumb_im, None)

            (ASSETS_DIR / main_name).write_bytes(main_data)
            (ASSETS_DIR / thumb_name).write_bytes(thumb_data)

        config.append({"id": avatar_id, "main": main_name, "thumb": thumb_name})
        before_str = f"{orig_w}x{orig_h} ({orig_bytes/1024:.0f} KB)"
        main_str = f"{target_main}px ({len(main_data)/1024:.1f} KB)"
        thumb_str = f"{target_thumb}px ({len(thumb_data)/1024:.1f} KB)"
        print(f"{avatar_id:<10} {src_path.name:<55} {before_str:>18} {main_str:>14} {thumb_str:>14}")

    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(config)} entries to {CONFIG_PATH}")
    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print(f" - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

