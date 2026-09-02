"""venv 쪽 렌더 러너: pipeline/scenes/<scene>.py를 헤드리스 Blender로 실행한다.

bpy를 import하지 않는다. 장면 스크립트와는 CLI 인자와 파일로만 통신한다.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import BLENDER_BIN, PROJECT_ROOT

SCENES_DIR = PROJECT_ROOT / "pipeline" / "scenes"


def scene_script(scene: str) -> Path:
    path = SCENES_DIR / f"{scene}.py"
    if not path.exists():
        raise FileNotFoundError(f"장면 스크립트가 없습니다: {path}")
    return path


def _base_cmd(scene: str) -> list[str]:
    return [BLENDER_BIN, "--background", "--python-exit-code", "1",
            "--python", str(scene_script(scene)), "--"]


def render_clip(scene: str, camera: str, out_path, *, frame_start=1, frame_end=1,
                resolution=(1920, 1080), fps=24, samples=64, still=False, event="none") -> Path:
    out_path = Path(out_path).resolve()
    if out_path.exists():  # 재실행 안전: 밤새 렌더가 중간에 죽어도 같은 명령으로 이어 간다
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 임시 하위 디렉터리에 렌더한 뒤 성공했을 때만 최종 경로로 원자적으로 옮긴다.
    # mp4는 Blender가 FFmpeg 먹서로 프레임마다 스트리밍 기록하므로, 도중에 죽으면
    # 손상된 파일이 최종 경로에 남아 다음 실행이 완료된 산출물로 오판할 수 있다.
    # 임시 파일명은 최종 파일과 동일하게 유지해 확장자(컨테이너/코덱 처리)를 바꾸지 않는다.
    tmp_dir = out_path.parent / f".{out_path.name}.tmp"
    if tmp_dir.exists():  # 이전 실행이 죽으며 남긴 잔여물
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    tmp_path = tmp_dir / out_path.name
    cmd = _base_cmd(scene) + [
        "--camera", camera, "--out", str(tmp_path),
        "--frame-start", str(frame_start), "--frame-end", str(frame_end),
        "--resolution", f"{resolution[0]}x{resolution[1]}",
        "--fps", str(fps), "--samples", str(samples), "--event", event,
    ]
    if still:
        cmd.append("--still")
    try:
        subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        if not tmp_path.exists():
            raise RuntimeError(f"렌더가 산출물을 만들지 못했습니다: {tmp_path}")
        os.replace(tmp_path, out_path)  # 같은 파일시스템 안의 원자적 이동
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
    return out_path


def check_scene(scene: str, camera="wide", event="none", frame_end=4) -> dict:
    cmd = _base_cmd(scene) + ["--camera", camera, "--event", event,
                              "--frame-end", str(frame_end), "--check"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=PROJECT_ROOT)
    for line in proc.stdout.splitlines():
        if line.startswith("CHECK:"):
            return json.loads(line[len("CHECK:"):])
    raise RuntimeError(f"CHECK 출력이 없습니다:\n{proc.stdout[-2000:]}")


if __name__ == "__main__":
    # 예: python -m pipeline.render_shot bus_stop wide out.png --still
    scene, camera, out = sys.argv[1:4]
    print(render_clip(scene, camera, out, resolution=(960, 540), samples=16,
                      still="--still" in sys.argv))
