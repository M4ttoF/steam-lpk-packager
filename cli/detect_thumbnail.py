#!/usr/bin/env python3
"""
detect_thumbnail.py — Fast PIL-based bad thumbnail detector.

A "bad" thumbnail is the auto-generated progress indicator image that
Steam Workshop uses when no custom thumbnail was provided:
  - Pure white background
  - Black text only (e.g. "109 • 09/15")
  - No character art, no color

Detection uses two quick image statistics — no OCR, no Tesseract needed.

Usage:
    py detect_thumbnail.py <path_to_png>

Exit codes:
    0  — always (result printed to stdout: "BAD" or "OK")
    1  — file not found or unreadable error

Batch usage from another script:
    import subprocess
    r = subprocess.run(['py', 'detect_thumbnail.py', path], capture_output=True, text=True)
    is_bad = r.stdout.strip() == 'BAD'
"""

import sys
import os

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Missing deps. Run: pip install Pillow numpy", file=sys.stderr)
    sys.exit(1)


# ─── Thresholds ──────────────────────────────────────────────────────────────
# Ratio of near-white pixels required to flag as bad.
# Real bad thumbnails measure ~0.896 white ratio (thick black text covers ~10%).
# Setting threshold at 0.80 gives comfortable headroom vs. real character art.
WHITE_PIXEL_RATIO_THRESHOLD = 0.80
WHITE_BRIGHTNESS_CUTOFF = 230

# Max average per-pixel channel spread (max_channel - min_channel).
# Real bad thumbnails are pure B&W so saturation = 0.0 exactly.
# Color character art will have avg_saturation >> 15.
COLOR_SATURATION_THRESHOLD = 10
# ─────────────────────────────────────────────────────────────────────────────


def is_default_thumbnail(img_path: str) -> tuple[bool, dict]:
    """
    Returns (is_bad: bool, stats: dict) where stats contains diagnostic values.
    """
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img, dtype=np.uint8)

    total_pixels = arr.shape[0] * arr.shape[1]

    # Stat 1: White pixel ratio
    brightness = arr.mean(axis=2)
    white_pixels = np.sum(brightness > WHITE_BRIGHTNESS_CUTOFF)
    white_ratio = white_pixels / total_pixels

    # Stat 2: Average color saturation (max channel - min channel per pixel)
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    max_ch = np.maximum(np.maximum(r, g), b)
    min_ch = np.minimum(np.minimum(r, g), b)
    avg_saturation = float(np.mean(max_ch - min_ch))

    # Stat 3: File size check (bad thumbnails are simple B&W text, always < 50KB. Real art is > 60KB)
    file_size_kb = os.path.getsize(img_path) / 1024.0

    is_bad = (
        white_ratio > WHITE_PIXEL_RATIO_THRESHOLD
        and avg_saturation < COLOR_SATURATION_THRESHOLD
        and file_size_kb < 50.0
    )

    stats = {
        "white_ratio":    round(white_ratio, 4),
        "avg_saturation": round(avg_saturation, 2),
        "file_size_kb":   round(file_size_kb, 1),
        "resolution":     f"{img.width}x{img.height}",
    }
    return is_bad, stats


def main():
    if len(sys.argv) < 2:
        print("Usage: py detect_thumbnail.py <path_to_png>", file=sys.stderr)
        sys.exit(1)

    img_path = sys.argv[1]

    if not os.path.exists(img_path):
        print(f"[Error] File not found: {img_path}", file=sys.stderr)
        sys.exit(1)

    try:
        bad, stats = is_default_thumbnail(img_path)
    except Exception as e:
        print(f"[Error] Could not analyze image: {e}", file=sys.stderr)
        sys.exit(1)

    result = "BAD" if bad else "OK"
    print(result)

    # Verbose diagnostics when running interactively (not piped)
    if sys.stdout.isatty():
        print(f"  white_ratio    : {stats['white_ratio']:.4f}  (threshold > {WHITE_PIXEL_RATIO_THRESHOLD})")
        print(f"  avg_saturation : {stats['avg_saturation']:.2f}  (threshold < {COLOR_SATURATION_THRESHOLD})")
        print(f"  file_size_kb   : {stats['file_size_kb']:.1f}  (threshold < 50.0)")
        print(f"  resolution     : {stats['resolution']}")
        print(f"  → {img_path}")


if __name__ == "__main__":
    main()
