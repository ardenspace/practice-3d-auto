from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.depth import extract_depth


def _make_test_image(path: Path) -> Path:
    # Use rich texture (random RGB noise) so depth model produces varied output.
    # A simple gradient may yield limited depth variation even with full precision.
    rng = np.random.default_rng(0)
    rgb = rng.integers(0, 255, (96, 128, 3), dtype=np.uint8)
    Image.fromarray(rgb, mode="RGB").save(path)
    return path


def test_extract_depth_writes_16bit_png_same_size(tmp_path):
    src = _make_test_image(tmp_path / "src.png")
    out = extract_depth(src, tmp_path / "depth.png")

    assert out.exists()
    depth_img = Image.open(out)
    assert depth_img.size == (128, 96)
    assert depth_img.mode == "I;16"
    arr = np.array(depth_img)
    assert arr.min() == 0 and arr.max() == 65535  # 전 구간 정규화
    # Verify full precision (predicted_depth, not 8-bit depth) was used.
    # With full-precision float tensors, we expect many more than 256 distinct levels.
    assert len(np.unique(arr)) > 256, f"Only {len(np.unique(arr))} distinct values; indicates 8-bit quantization"
