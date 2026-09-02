"""Blender 헤드리스 렌더 러너. 프리뷰(스틸 1장)와 풀(애니메이션)을 분리한다."""

import json
import subprocess
import sys
from pathlib import Path

from pipeline.config import BLENDER_BIN, PROJECT_ROOT

SCENE_SCRIPT = PROJECT_ROOT / "pipeline" / "blender" / "parallax_scene.py"


def render_shot(spec_path: Path, mode: str) -> Path:
    if mode not in ("preview", "full"):
        raise ValueError(f"mode는 preview|full 중 하나여야 합니다: {mode}")

    spec = json.loads(Path(spec_path).read_text())
    suffix = "_preview.png" if mode == "preview" else ".mp4"
    out_path = (PROJECT_ROOT / spec["out_dir"] / f"{spec['name']}{suffix}").resolve()

    if out_path.exists():  # 재실행 안전: 이미 산출물이 있으면 건너뛴다
        return out_path

    subprocess.run(
        [BLENDER_BIN, "--background", "--python", str(SCENE_SCRIPT),
         "--", str(Path(spec_path).resolve()), mode],
        check=True,
        cwd=PROJECT_ROOT,
    )
    if not out_path.exists():
        raise RuntimeError(f"렌더가 산출물을 만들지 못했습니다: {out_path}")
    return out_path


if __name__ == "__main__":
    print(render_shot(Path(sys.argv[1]), sys.argv[2]))
