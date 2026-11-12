#!/usr/bin/env python3
"""
Build processed avatar assets (512x512 main + 128x128 thumb WebP) and avatars.json config
from the project's top-level Avatar/ folder without modifying originals.

Uses face detection (OpenCV Haar cascades) to:
1. Measure already well-framed half-body avatars and compute their median framing standard
   (face height %, top margin above face %, horizontal face center %).
2. Crop every avatar to a square matching that half-body standard without stretching or
   silent upscaling, flagging any image with no face or tight head/edge crop for review.
"""

from __future__ import annotations

import io
import json
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "avatars"
CONFIG_PATH = ASSETS_DIR / "avatars.json"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
MAIN_SIZE = 512
THUMB_SIZE = 128
MAX_MAIN_BYTES = 100 * 1024  # 100 KB target

_ALT2 = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")
_DEFAULT = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def find_avatar_dir(root: Path) -> Path:
    for entry in root.iterdir():
        if entry.is_dir() and entry.name.lower() == "avatar":
            return entry
    raise FileNotFoundError(f"Could not find an 'avatar' folder (case-insensitive) inside {root}")


def detect_face(im: Image.Image) -> tuple[tuple[int, int, int, int] | None, str]:
    """Detect primary face in upper 60% of image. Returns ((x, y, fw, fh), confidence)."""
    w, h = im.size
    rgb = np.array(im.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    upper = gray[: int(h * 0.60), :]
    min_side = max(48, int(min(w, h) * 0.07))

    faces = _ALT2.detectMultiScale(upper, 1.05, 5, minSize=(min_side, min_side))
    if len(faces) > 0:
        x, y, fw, fh = max(faces, key=lambda f: int(f[2]) * int(f[3]))
        return (int(x), int(y), int(fw), int(fh)), "high"

    faces = _DEFAULT.detectMultiScale(upper, 1.05, 4, minSize=(min_side, min_side))
    if len(faces) > 0:
        x, y, fw, fh = max(faces, key=lambda f: int(f[2]) * int(f[3]))
        return (int(x), int(y), int(fw), int(fh)), "medium"

    faces = _DEFAULT.detectMultiScale(upper, 1.05, 3, minSize=(max(64, int(min(w, h) * 0.10)), max(64, int(min(w, h) * 0.10))))
    if len(faces) > 0:
        x, y, fw, fh = max(faces, key=lambda f: int(f[2]) * int(f[3]))
        return (int(x), int(y), int(fw), int(fh)), "low"

    return None, "none"


def compute_framing_crop(
    w: int,
    h: int,
    face: tuple[int, int, int, int] | None,
    confidence: str,
    std_face_pct: float,
    std_top_pct: float,
    std_cx_pct: float,
    filename: str,
) -> tuple[tuple[int, int, int, int], str | None]:
    if face is None:
        side = min(w, h)
        left = (w - side) // 2
        top = int((h - side) * 0.10) if h > w else 0
        box = (left, top, left + side, top + side)
        return box, f"REVIEW ({filename}): no face detected; suggested top-biased crop {box}."

    x, y, fw, fh = face
    ideal_side = int(round(fh / std_face_pct))
    side = min(w, h, max(ideal_side, min(w, h) // 3))

    face_cx = x + fw / 2.0
    desired_left = int(round(face_cx - side * std_cx_pct))
    desired_top = int(round(y - side * std_top_pct))

    left = max(0, min(w - side, desired_left))
    top = max(0, min(h - side, desired_top))
    box = (left, top, left + side, top + side)

    flags: list[str] = []
    if side < MAIN_SIZE:
        flags.append(f"crop {side}px < {MAIN_SIZE}px (would upscale/blur)")
    if desired_top < -int(0.03 * side):
        flags.append("top margin tight (verify head/crown not clipped)")
    if confidence == "low":
        flags.append("low-confidence face detection (verify crop)")
    if max(w / h, h / w) > 1.45:
        flags.append(f"wide/tall aspect {w}x{h}")

    flag_msg = f"REVIEW ({filename}): {'; '.join(flags)}; crop={box}." if flags else None
    return box, flag_msg


def encode_webp_under_limit(im: Image.Image, max_bytes: int | None = None) -> bytes:
    data = b""
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

    # Pass 1: Detect faces & measure well-framed half-body avatars
    detections: list[tuple[Path, tuple[int, int], tuple[int, int, int, int] | None, str]] = []
    well_fh_pcts: list[float] = []
    well_top_pcts: list[float] = []
    well_cx_pcts: list[float] = []

    for src_path in files:
        with Image.open(src_path) as raw:
            im = ImageOps.exif_transpose(raw).convert("RGBA")
            w, h = im.size
            face, conf = detect_face(im)
        detections.append((src_path, (w, h), face, conf))
        if face is not None and conf in ("high", "medium"):
            x, y, fw, fh = face
            fh_pct = fh / h
            if fh_pct >= 0.16:
                well_fh_pcts.append(fh_pct)
                well_top_pcts.append(y / h)
                well_cx_pcts.append((x + fw / 2.0) / w)

    std_face_pct = statistics.median(well_fh_pcts) if well_fh_pcts else 0.26
    std_top_pct = statistics.median(well_top_pcts) if well_top_pcts else 0.13
    std_cx_pct = 0.50  # center face horizontally in final square

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in ASSETS_DIR.glob("avatar-*.webp"):
        stale.unlink()

    config: list[dict[str, str]] = []
    warnings: list[str] = []

    print(f"Source folder: {src_dir}")
    print(f"Output folder: {ASSETS_DIR}")
    print(
        f"Median half-body standard (from {len(well_fh_pcts)} well-framed avatars): "
        f"face_height={std_face_pct*100:.1f}%, top_margin={std_top_pct*100:.1f}%, horiz_center={std_cx_pct*100:.1f}%\n"
    )
    print(f"{'ID':<10} {'Original File':<48} {'Before':>17} {'Crop Box':>21} {'Main (512)':>14} {'Thumb (128)':>14} {'Flag'}")
    print("-" * 136)

    for idx, (src_path, (orig_w, orig_h), face, conf) in enumerate(detections, start=1):
        avatar_id = f"avatar-{idx:02d}"
        main_name = f"{avatar_id}.webp"
        thumb_name = f"{avatar_id}-thumb.webp"

        orig_bytes = src_path.stat().st_size
        crop_box, crop_warn = compute_framing_crop(
            orig_w, orig_h, face, conf, std_face_pct, std_top_pct, std_cx_pct, src_path.name
        )
        if orig_w < MAIN_SIZE or orig_h < MAIN_SIZE:
            warnings.append(f"SMALL IMAGE ({src_path.name}): {orig_w}x{orig_h} < {MAIN_SIZE}px; will NOT upscale.")
        if crop_warn:
            warnings.append(crop_warn)

        with Image.open(src_path) as raw:
            im = ImageOps.exif_transpose(raw).convert("RGBA")
            sq = im.crop(crop_box)
            # Do not upscale smaller crops without warning; keep min(MAIN_SIZE, sq.width)
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
        crop_str = f"({crop_box[0]},{crop_box[1]},{crop_box[2]},{crop_box[3]})"
        main_str = f"{target_main}px ({len(main_data)/1024:.1f} KB)"
        thumb_str = f"{target_thumb}px ({len(thumb_data)/1024:.1f} KB)"
        flag_short = "REVIEW" if crop_warn else "OK"
        print(f"{avatar_id:<10} {src_path.name[:48]:<48} {before_str:>17} {crop_str:>21} {main_str:>14} {thumb_str:>14} {flag_short}")

    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(config)} entries to {CONFIG_PATH}")
    if warnings:
        print("\nREVIEW FLAGS / WARNINGS:")
        for w in warnings:
            print(f" - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
