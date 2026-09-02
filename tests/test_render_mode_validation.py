"""mode 오타 방어: 잘못된 mode 값은 Blender를 띄우기 전에 즉시 에러로 죽어야 한다.

"layerd"/"Layered" 같은 오타가 `spec.get("mode", "relief") == "layered"` 비교를 통해
조용히 relief로 새는 걸 막는다. Blender 기동 전에 죽으므로 빠르게 끝난다.
"""

import json

import pytest

from pipeline.render import render_shot


def _spec(tmp_path, **overrides):
    spec = {
        "image": str(tmp_path / "src.png"),
        "depth": str(tmp_path / "depth.png"),
        "out_dir": str(tmp_path / "renders"),
        "name": "bad_mode",
        "resolution": [320, 180],
        "fps": 12,
        "duration_s": 1,
        "depth_strength": 0.3,
        "camera": {"move": "push_in", "amplitude": 0.15, "sway": 0.0, "loop": False},
        "fog_density": 0.0,
    }
    spec.update(overrides)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))
    return spec_path


@pytest.mark.parametrize("bad_mode", ["layerd", "Layered", "relief ", "RELIEF", "2d"])
def test_render_shot_rejects_invalid_mode(tmp_path, bad_mode):
    spec_path = _spec(tmp_path, mode=bad_mode)
    with pytest.raises(ValueError):
        render_shot(spec_path, "preview")


def test_render_shot_missing_mode_still_defaults_to_relief(tmp_path):
    """mode 키가 아예 없는 v1 스펙은 검증을 통과해야 한다(하위 호환)."""
    from pipeline.render import _validate_spec_mode

    spec = json.loads(_spec(tmp_path).read_text())
    assert "mode" not in spec
    _validate_spec_mode(spec)  # 에러 없이 통과해야 함
