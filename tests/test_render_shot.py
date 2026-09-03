import subprocess
from pathlib import Path

import pytest

import pipeline.render_shot as render_shot
from pipeline.render_shot import check_scene, render_clip, scene_script


def test_scene_script_rejects_unknown_scene():
    with pytest.raises(FileNotFoundError):
        scene_script("no_such_scene")


def test_check_scene_reports_bus_stop_objects():
    info = check_scene("bus_stop", camera="wide")
    for name in ("road", "sidewalk", "lamp_post", "lamp_head", "bench_seat", "sign_board",
                 "bin", "marble_glass", "shelter_roof"):
        assert name in info["objects"], name
    assert {"wide", "shelter", "marble", "puddle"} <= set(info["cameras"])


def test_render_clip_still_is_idempotent(tmp_path):
    out = tmp_path / "wide.png"
    first = render_clip("bus_stop", "wide", out, resolution=(160, 90), samples=4, still=True)
    assert first.exists()
    mtime = first.stat().st_mtime
    second = render_clip("bus_stop", "wide", out, resolution=(160, 90), samples=4, still=True)
    assert second == first and second.stat().st_mtime == mtime


def test_render_clip_leaves_no_partial_output_on_failed_render(tmp_path):
    out = tmp_path / "wide.mp4"
    with pytest.raises(subprocess.CalledProcessError):
        render_clip("bus_stop", "no_such_camera", out, resolution=(160, 90), samples=4,
                    frame_start=1, frame_end=1)
    assert not out.exists()
    assert not (out.parent / f".{out.name}.tmp").exists()


def test_render_clip_animation_writes_mp4_and_removes_frame_dir(tmp_path):
    """할 일 2 성질 1: 애니메이션을 렌더하면 mp4가 만들어지고 PNG 작업 디렉터리가 남지 않는다."""
    out = tmp_path / "wide.mp4"
    result = render_clip("bus_stop", "wide", out, frame_start=1, frame_end=6,
                         resolution=(160, 90), fps=12, samples=4)
    assert result == out
    assert out.exists() and out.stat().st_size > 5_000
    assert not (tmp_path / "wide.mp4.frames").exists()


def _spy_on_encode(monkeypatch):
    """_encode_frames_to_mp4 직전(=render_clip이 frames_dir를 지우기 직전)의 프레임 mtime을 캡처한다.

    render_clip은 성공하면 frames_dir를 지워 버리므로, 재개가 실제로 일어났는지 보려면
    지워지기 직전 순간을 가로채야 한다. 원래 함수는 그대로 호출해 동작은 바꾸지 않는다.
    """
    captured = {}
    original = render_shot._encode_frames_to_mp4

    def spy(frames_dir, dest, **kwargs):
        captured["mtimes"] = {f.name: f.stat().st_mtime for f in render_shot._frame_files(frames_dir)}
        return original(frames_dir, dest, **kwargs)

    monkeypatch.setattr(render_shot, "_encode_frames_to_mp4", spy)
    return captured


def test_render_clip_resume_only_renders_missing_frames(tmp_path, monkeypatch):
    """할 일 2 성질 2: 프레임 일부만 있는 상태에서 다시 부르면 없는 프레임만 렌더한다.

    6프레임을 직접 채운 뒤 2개(frame_0002, frame_0004)를 지워 "렌더하다 만" 상태를
    흉내 낸다. render_clip을 다시 부르면 _drop_broken_last_frame이 가장 큰 번호(0006)도
    함께 지우므로, 다시 그려지는 것은 0002·0004·0006 세 개고 나머지(0001·0003·0005)는
    mtime이 그대로여야 한다.
    """
    frames_dir = tmp_path / "wide.mp4.frames"
    render_shot._render_frames_to_dir("bus_stop", "wide", frames_dir, frame_start=1, frame_end=6,
                                      resolution=(160, 90), fps=12, samples=4, event="none")
    files_before = {f.name: f.stat().st_mtime for f in render_shot._frame_files(frames_dir)}
    assert len(files_before) == 6

    (frames_dir / "frame_0002.png").unlink()
    (frames_dir / "frame_0004.png").unlink()

    captured = _spy_on_encode(monkeypatch)
    out = tmp_path / "wide.mp4"
    render_clip("bus_stop", "wide", out, frame_start=1, frame_end=6,
               resolution=(160, 90), fps=12, samples=4)

    assert out.exists()
    after = captured["mtimes"]
    assert set(after) == set(files_before)  # 6개 전부 다시 있다 — 빠짐없이 채워졌다
    for name in ("frame_0001.png", "frame_0003.png", "frame_0005.png"):
        assert after[name] == files_before[name], f"{name}는 다시 렌더되면 안 된다"
    for name in ("frame_0002.png", "frame_0004.png", "frame_0006.png"):
        assert after[name] > files_before[name], f"{name}는 새로 렌더돼야 한다"


def test_render_clip_drops_last_frame_before_resuming(tmp_path, monkeypatch):
    """할 일 2 성질 3: 마지막 PNG 하나를 지우고 시작하는 동작이 실제로 일어난다.

    프레임이 전부(0001~0004) 있는 상태에서 다시 불러도, 가장 번호가 큰 0004는 깨졌을
    수 있다는 전제로 무조건 다시 렌더돼야 한다. 나머지는 손대지 않는다.
    """
    frames_dir = tmp_path / "wide.mp4.frames"
    render_shot._render_frames_to_dir("bus_stop", "wide", frames_dir, frame_start=1, frame_end=4,
                                      resolution=(160, 90), fps=12, samples=4, event="none")
    files_before = {f.name: f.stat().st_mtime for f in render_shot._frame_files(frames_dir)}
    assert len(files_before) == 4

    captured = _spy_on_encode(monkeypatch)
    out = tmp_path / "wide.mp4"
    render_clip("bus_stop", "wide", out, frame_start=1, frame_end=4,
               resolution=(160, 90), fps=12, samples=4)

    after = captured["mtimes"]
    assert set(after) == set(files_before)
    for name in ("frame_0001.png", "frame_0002.png", "frame_0003.png"):
        assert after[name] == files_before[name], f"{name}는 다시 렌더되면 안 된다"
    assert after["frame_0004.png"] > files_before["frame_0004.png"]


def test_frame_files_numeric_sort_mixed_digit_widths(tmp_path):
    """_frame_files가 파일 이름에서 숫자를 추출해 정수로 정렬해야 한다.

    자리수가 섞여 있을 때도 올바르게 정렬되어야 한다. 예: frame_0009.png < frame_0010.png < frame_9999.png < frame_10000.png
    문자열 정렬이었다면 frame_10000.png가 frame_9999.png보다 앞에 오므로 실패한다.
    """
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    # 자리수가 섞인 파일 이름 생성
    test_files = ["frame_0009.png", "frame_10000.png", "frame_0010.png", "frame_9999.png"]
    for name in test_files:
        (frames_dir / name).touch()

    result = render_shot._frame_files(frames_dir)
    result_names = [f.name for f in result]

    # 정수 정렬이 올바른 순서
    expected = ["frame_0009.png", "frame_0010.png", "frame_9999.png", "frame_10000.png"]
    assert result_names == expected, f"정렬 순서가 틀렸습니다. 기대: {expected}, 받음: {result_names}"
