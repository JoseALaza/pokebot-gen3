#!/usr/bin/env python3
"""
quick_cv_upscale.py — rule-based OpenCV variants (no Pillow downgrade)
deps:  pip install pillow opencv-python numpy
call:
    python quick_cv_upscale.py frame.png
out:
    frame_variants/
        frame_2x_scale2x.png
        frame_3x_scale2x.png
        frame_4x_scale2x.png
        frame_2x_lanczos.png
        …
"""

from pathlib import Path
import sys, numpy as np, cv2
from PIL import Image, ImageFilter, ImageOps, ImageEnhance

# --------------------------------------------------------------------
def scale2x(arr: np.ndarray) -> np.ndarray:
    """OpenCV's nearest up → gaussian blur → sharpen clone of classic Scale2×."""
    up = cv2.resize(arr, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    blur = cv2.GaussianBlur(up, (3, 3), 0)
    sharp = cv2.addWeighted(up, 1.5, blur, -0.5, 0)
    return sharp

def resize_cv(arr: np.ndarray, factor: int, interp) -> np.ndarray:
    return cv2.resize(arr, None, fx=factor, fy=factor, interpolation=interp)

# --------------------------------------------------------------------
def pil2cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)

def cv2pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))

# (func, tag)
UPSCALE_FUNCS = [
    (lambda a,f: scale2x(a) if f==2 else resize_cv(a,f,cv2.INTER_NEAREST), "scale2x"),
    (lambda a,f: resize_cv(a,f,cv2.INTER_LANCZOS4),                     "lanczos"),
]

SCALES = [2,3,4]

# --------------------------------------------------------------------
def main(fp: Path):
    if not fp.exists():
        sys.exit("file not found")
    base = Image.open(fp).convert("RGB")
    arr  = pil2cv(base)

    outdir = fp.with_name(f"{fp.stem}_variants")
    outdir.mkdir(exist_ok=True)

    for factor in SCALES:
        for fn, tag in UPSCALE_FUNCS:
            up_arr = fn(arr, factor)
            img    = cv2pil(up_arr)
            img.save(outdir / f"{fp.stem}_{factor}x_{tag}.png", optimize=True)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: quick_cv_upscale.py frame.png")
    main(Path(sys.argv[1]))
