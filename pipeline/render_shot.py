"""venv 쪽 렌더 러너: pipeline/scenes/<scene>.py를 헤드리스 Blender로 실행한다.

bpy를 import하지 않는다. 장면 스크립트와는 CLI 인자와 파일로만 통신한다.
"""

import json
import os
import re
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


def extract_frame_number(path: Path) -> int | None:
    """파일 이름에서 frame_XXXX.png의 XXXX 부분을 정수로 추출한다.

    숫자로 파싱되지 않으면 None을 반환해 필터링된다.
    """
    match = re.search(r"frame_(\d+)\.png", path.name)
    if match:
        return int(match.group(1))
    return None


def _frame_files(frames_dir: Path) -> list[Path]:
    """프레임 파일을 숫자로 정렬하여 반환한다.

    파일 이름에서 frame_XXXX.png의 XXXX 부분을 정수로 파싱해 정렬한다.
    자리수가 다르면 문자열 정렬이 틀린다 (예: "frame_10000.png" < "frame_9999.png").
    숫자로 파싱되지 않는 파일은 결과에서 제외한다. 그렇지 않으면 _drop_broken_last_frame이
    진짜 마지막 프레임 대신 잘못된 파일을 지운다.
    """
    files = list(frames_dir.glob("frame_*.png"))
    # 파싱 가능한 파일만 필터링
    valid_files = [f for f in files if extract_frame_number(f) is not None]
    # 프레임 번호로 정렬
    return sorted(valid_files, key=extract_frame_number)


def _drop_broken_last_frame(frames_dir: Path) -> None:
    """재개 전, 가장 번호가 큰 PNG 파일 하나를 지운다.

    렌더 도중 프로세스가 죽으면 그 순간 쓰고 있던 프레임 파일이 다 쓰이지 못한 채로
    남을 수 있다. 파일이 존재한다는 사실만으로는 완성 여부를 알 수 없으므로, 재개할
    때마다 가장 번호가 큰 파일을 무조건 하나 지우고 다시 렌더한다. 이미 완성된
    프레임이었다면 다시 렌더하는 비용만 더 들 뿐이지만, 손상된 프레임이 완성본 mp4에
    섞이는 쪽이 그보다 훨씬 나쁘다.
    """
    files = _frame_files(frames_dir)
    if files:
        files[-1].unlink()


def _render_frames_to_dir(scene: str, camera: str, frames_dir: Path, *, frame_start: int, frame_end: int,
                          resolution: tuple[int, int], fps: int, samples: int, event: str) -> None:
    """Blender를 불러 frames_dir 안의 없는 프레임만 채운다.

    scene.render.use_overwrite=False(common.render_animation)이므로 이미 있는 프레임
    파일은 건너뛴다 — 프레임 단위 재개는 전적으로 이 성질에 의존한다. frames_dir가
    미리 없어도 된다 — Blender가 filepath(frame_ 접두어)를 쓰며 만든다.
    """
    cmd = _base_cmd(scene) + [
        "--camera", camera, "--out", str(frames_dir / "frame_"),
        "--frame-start", str(frame_start), "--frame-end", str(frame_end),
        "--resolution", f"{resolution[0]}x{resolution[1]}",
        "--fps", str(fps), "--samples", str(samples), "--event", event,
    ]
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def _encode_frames_to_mp4(frames_dir: Path, dest: Path, *, frame_start: int, frame_end: int, fps: int) -> None:
    """PNG 연속 이미지를 ffmpeg으로 mp4 하나로 만든다.

    이 mp4는 중간 산출물이고 pipeline.assemble이 나중에 다시 인코딩하므로, 지금까지
    common.render_animation이 Blender의 FFmpeg 먹서로 쓰던 것과 같은 수준의 고품질
    설정(constant_rate_factor="PERC_LOSSLESS")에 대응하는 낮은 crf를 쓴다.

    인코딩 전에 frame_start~frame_end 프레임이 모두 있는지 확인한다. ffmpeg의 image2
    디먹서는 번호가 끊기는 지점에서 조용히 멈추고 exit 0을 내므로(예: 10프레임 중
    가운데 하나가 없으면 거기까지만 읽고 성공으로 끝난다), 확인 없이 넘기면 잘린 mp4가
    최종 산출물로 승격된다.
    """
    present = {n for n in (extract_frame_number(f) for f in _frame_files(frames_dir)) if n is not None}
    missing = sorted(set(range(frame_start, frame_end + 1)) - present)
    if missing:
        preview = ", ".join(str(n) for n in missing[:5])
        more = f" 외 {len(missing) - 5}개" if len(missing) > 5 else ""
        raise RuntimeError(
            f"{frames_dir}에 프레임이 {len(missing)}개 빠졌습니다 (번호: {preview}{more}). "
            f"인코딩을 중단합니다 — ffmpeg이 조용히 잘린 mp4를 만들 수 있습니다."
        )
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-start_number", str(frame_start),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-frames:v", str(frame_end - frame_start + 1),
        "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
        str(dest),
    ]
    subprocess.run(cmd, check=True)


def _atomic_produce(out_path: Path, produce) -> Path:
    """produce(tmp_path)로 tmp_path에 산출물을 만들고, 성공했을 때만 out_path로 원자적으로 옮긴다.

    도중에 죽으면 손상된 파일이 최종 경로에 남아 다음 실행이 완료된 산출물로 오판할
    수 있으므로, 임시 하위 디렉터리에 먼저 만든다. 임시 파일명은 최종 파일과 동일하게
    유지해 확장자(컨테이너/코덱 처리)를 바꾸지 않는다.
    """
    tmp_dir = out_path.parent / f".{out_path.name}.tmp"
    if tmp_dir.exists():  # 이전 실행이 죽으며 남긴 잔여물
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    tmp_path = tmp_dir / out_path.name
    try:
        produce(tmp_path)
        if not tmp_path.exists():
            raise RuntimeError(f"렌더가 산출물을 만들지 못했습니다: {tmp_path}")
        os.replace(tmp_path, out_path)  # 같은 파일시스템 안의 원자적 이동
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
    return out_path


def _manifest_path(out_path: Path) -> Path:
    return out_path.parent / f"{out_path.name}.json"


def _expected_manifest(scene, camera, event, frame_start, frame_end, resolution, fps, samples, still) -> dict:
    return {
        "scene": scene, "camera": camera, "event": event,
        "frame_start": frame_start, "frame_end": frame_end,
        "resolution": list(resolution), "fps": fps, "samples": samples, "still": still,
        "script_mtime": scene_script(scene).stat().st_mtime_ns,
    }


def render_clip(scene: str, camera: str, out_path, *, frame_start=1, frame_end=1,
                resolution=(1920, 1080), fps=24, samples=64, still=False, event="none") -> Path:
    out_path = Path(out_path).resolve()
    manifest_path = _manifest_path(out_path)
    expected = _expected_manifest(scene, camera, event, frame_start, frame_end, resolution, fps, samples, still)

    if out_path.exists():  # 재실행 안전: 밤새 렌더가 중간에 죽어도 같은 명령으로 이어 간다
        if not manifest_path.exists():
            # 매니페스트 도입 이전에 만들어진 클립(예: episodes/dream-bus-stop/renders/의
            # 사용자 승인 클립들). 정의와 맞는지는 별도 리뷰에서 ffprobe로 이미 확인했으므로
            # 예외를 던지지 않고 경고만 남긴 뒤 그대로 재사용한다.
            print(f"경고: {out_path}에 렌더 매니페스트가 없습니다 (이 기능 이전에 만들어진 클립). 그대로 재사용합니다.")
            return out_path
        actual = json.loads(manifest_path.read_text())
        if actual != expected:
            diffs = {key: {"기존": actual.get(key), "새 정의": expected[key]}
                    for key in expected if actual.get(key) != expected[key]}
            raise RuntimeError(
                f"{out_path}의 렌더 파라미터가 지금의 회차 정의와 다릅니다: {diffs}. "
                f"지우고 다시 렌더하십시오: {out_path} (매니페스트: {manifest_path})"
            )
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if still:
        def produce(tmp_path):
            cmd = _base_cmd(scene) + [
                "--camera", camera, "--out", str(tmp_path),
                "--frame-start", str(frame_start), "--frame-end", str(frame_end),
                "--resolution", f"{resolution[0]}x{resolution[1]}",
                "--fps", str(fps), "--samples", str(samples), "--event", event,
                "--still",
            ]
            subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        result = _atomic_produce(out_path, produce)
        manifest_path.write_text(json.dumps(expected))  # 렌더 성공 뒤에만 쓴다 (먼저 쓰면 실패 후 재실행이 완료로 오판할 수 있다)
        return result

    # 애니메이션: Blender는 PNG 연속 이미지만 채우고, mp4 인코딩은 여기서 ffmpeg으로 한다.
    # PNG 작업 디렉터리(frames_dir)는 최종 mp4 "옆"에 예측 가능한 이름(<out>.frames/)으로
    # 둔다 — _atomic_produce의 tmp_dir(실패하면 통째로 지워지는 곳) 안에 두면 실패한 뒤
    # 재개할 자료가 함께 사라진다. 두 디렉터리는 서로 다른 생명주기를 가진다.
    frames_dir = out_path.parent / f"{out_path.name}.frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    _drop_broken_last_frame(frames_dir)
    _render_frames_to_dir(scene, camera, frames_dir, frame_start=frame_start, frame_end=frame_end,
                          resolution=resolution, fps=fps, samples=samples, event=event)

    def produce(tmp_path):
        _encode_frames_to_mp4(frames_dir, tmp_path, frame_start=frame_start, frame_end=frame_end, fps=fps)
    result = _atomic_produce(out_path, produce)
    shutil.rmtree(frames_dir)  # 인코딩에 성공했으니 PNG 작업 디렉터리는 지운다
    manifest_path.write_text(json.dumps(expected))  # 렌더 성공 뒤에만 쓴다
    return result


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
