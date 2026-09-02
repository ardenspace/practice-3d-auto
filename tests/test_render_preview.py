import json
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.render import render_shot


def _fixture(tmp_path: Path) -> Path:
    rng = np.random.default_rng(0)
    Image.fromarray(rng.integers(0, 255, (90, 160, 3), dtype=np.uint8)).save(
        tmp_path / "src.png"
    )
    grad = np.tile(np.linspace(0, 65535, 160, dtype=np.uint16), (90, 1))
    Image.fromarray(grad).save(tmp_path / "depth.png")

    spec = {
        "image": str(tmp_path / "src.png"),
        "depth": str(tmp_path / "depth.png"),
        "out_dir": str(tmp_path / "renders"),
        "name": "smoke",
        "resolution": [320, 180],
        "fps": 12,
        "duration_s": 1,
        "depth_strength": 0.3,
        "camera": {"move": "push_in", "amplitude": 0.15, "sway": 0.0, "loop": False},
        "fog_density": 0.05,
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))
    return spec_path


def test_preview_renders_single_still(tmp_path):
    out = render_shot(_fixture(tmp_path), "preview")
    assert out.exists() and out.suffix == ".png"
    assert Image.open(out).size == (320, 180)
