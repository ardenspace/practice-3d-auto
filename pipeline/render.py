"""Blender 헤드리스 렌더 러너. 프리뷰(스틸 1장)와 풀(애니메이션)을 분리한다."""

import json
import subprocess
import sys
from pathlib import Path

from pipeline.config import BLENDER_BIN, PROJECT_ROOT
from pipeline.layers import layers_json_path, split_layers

SCENE_SCRIPT = PROJECT_ROOT / "pipeline" / "blender" / "parallax_scene.py"
DEFAULT_N_LAYERS = 3


def _prepare_layers(spec: dict) -> Path:
    """layered 스펙의 레이어 산출물을 렌더 전에 만든다(이미 있으면 재사용).

    numpy/cv2가 필요한 작업이라 Blender 밖(venv)에서 끝내고, bpy 쪽에는 PNG와
    메타 JSON만 넘긴다.
    """
    image = (PROJECT_ROOT / spec["image"]).resolve()
    depth = (PROJECT_ROOT / spec["depth"]).resolve()
    n_layers = int(spec.get("n_layers", DEFAULT_N_LAYERS))

    meta_path = layers_json_path(image, n_layers)
    if meta_path.exists():
        return meta_path
    return split_layers(image, depth, meta_path.parent, n_layers)


def render_shot(spec_path: Path, mode: str) -> Path:
    if mode not in ("preview", "full"):
        raise ValueError(f"mode는 preview|full 중 하나여야 합니다: {mode}")

    spec = json.loads(Path(spec_path).read_text())
    suffix = "_preview.png" if mode == "preview" else ".mp4"
    out_path = (PROJECT_ROOT / spec["out_dir"] / f"{spec['name']}{suffix}").resolve()

    if out_path.exists():  # 재실행 안전: 이미 산출물이 있으면 건너뛴다
        return out_path

    # mode 미지정 스펙은 v1(단일 평면 부조)이므로 relief로 해석한다(하위 호환)
    if spec.get("mode", "relief") == "layered":
        _prepare_layers(spec)

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
