import subprocess
from pathlib import Path

import pytest

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
