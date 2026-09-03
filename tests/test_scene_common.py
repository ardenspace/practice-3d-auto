import json
import subprocess
from pathlib import Path

from PIL import Image

from pipeline.config import BLENDER_BIN, PROJECT_ROOT

SMOKE = PROJECT_ROOT / "tests" / "bpy_scripts" / "common_smoke.py"


def _run(extra):
    return subprocess.run(
        [BLENDER_BIN, "--background", "--python-exit-code", "1", "--python", str(SMOKE), "--", *extra],
        capture_output=True, text=True, check=True, cwd=PROJECT_ROOT,
    )


def test_common_helpers_render_a_still(tmp_path):
    out = tmp_path / "smoke.png"
    _run(["--out", str(out)])
    assert out.exists()
    img = Image.open(out)
    assert img.size == (160, 90)
    # 완전히 검거나 완전히 흰 이미지는 실패로 본다(조명·안개·컴포지터 중 무언가가 죽은 것)
    mean = sum(img.convert("L").get_flattened_data()) / (160 * 90)
    assert 3 < mean < 250


def test_common_check_dumps_json():
    proc = _run(["--check", "--out", "unused"])
    line = next(l for l in proc.stdout.splitlines() if l.startswith("CHECK:"))
    info = json.loads(line[len("CHECK:"):])
    assert "cube" in info["objects"] and "cam" in info["cameras"] and "lamp" in info["lights"]
    assert info["extra"] == {"smoke": True}
