import math
import subprocess

from pipeline.assemble import probe_duration, repeat_clip


def _color_clip(path, seconds, color="red"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"color=c={color}:s=160x90:r=24:d={seconds}",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_probe_duration(tmp_path):
    clip = _color_clip(tmp_path / "a.mp4", 2)
    assert math.isclose(probe_duration(clip), 2.0, abs_tol=0.1)


def test_repeat_clip_doubles_duration(tmp_path):
    clip = _color_clip(tmp_path / "a.mp4", 2)
    out = repeat_clip(clip, tmp_path / "aa.mp4", times=2)
    assert math.isclose(probe_duration(out), 4.0, abs_tol=0.15)
