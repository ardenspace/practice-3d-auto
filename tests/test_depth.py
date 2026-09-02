from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.depth import extract_depth


def _make_test_image(path: Path) -> Path:
    grad = np.tile(np.linspace(0, 255, 128, dtype=np.uint8), (96, 1))
    Image.merge("RGB", [Image.fromarray(grad)] * 3).save(path)
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
