import math
import subprocess
from pathlib import Path

from pipeline.assemble import assemble, build_sequence, probe_duration, repeat_clip


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


def test_build_sequence_cycles_loops_and_inserts_events():
    a, b, e = Path("a.mp4"), Path("b.mp4"), Path("e.mp4")
    durations = {a: 10.0, b: 10.0, e: 3.0}
    seq = build_sequence([a, b], [e], durations, target_s=45.0, event_every_s=20.0)
    assert seq[0] == a and seq[1] == b
    assert e in seq
    assert seq.count(e) == 2  # 20초마다 한 번씩
    assert sum(durations[c] for c in seq) >= 45.0


def test_build_sequence_without_events():
    a = Path("a.mp4")
    seq = build_sequence([a], [], {a: 7.0}, target_s=20.0, event_every_s=5.0)
    assert seq == [a, a, a]


def _tone(path, seconds):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=220:duration={seconds}", str(path)], check=True)
    return path


def test_assemble_crossfades_and_adds_audio(tmp_path):
    clips = [_color_clip(tmp_path / f"{c}.mp4", 3, c) for c in ("red", "green", "blue")]
    intro = _color_clip(tmp_path / "intro.mp4", 2, "black")
    outro = _color_clip(tmp_path / "outro.mp4", 2, "black")
    amb = _tone(tmp_path / "amb.wav", 1)
    out = assemble(clips, tmp_path / "final.mp4", intro=intro, outro=outro, ambience=amb, xfade_s=0.5)
    # 5클립 합계 13초, 크로스페이드 4번 × 0.5초 = 11초
    assert math.isclose(probe_duration(out), 11.0, abs_tol=0.3)
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
                             capture_output=True, text=True, check=True).stdout
    assert "audio" in streams and "video" in streams


def _stream_types(path) -> str:
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                          capture_output=True, text=True, check=True).stdout


def test_assemble_without_ambience_has_no_audio_stream(tmp_path):
    """ambience=None 분기(-an). 30분 완성본을 실제로 만든 경로인데 기존 테스트는 전부 ambience를 넘겼다."""
    clips = [_color_clip(tmp_path / f"{c}.mp4", 3, c) for c in ("red", "green", "blue")]
    out = assemble(clips, tmp_path / "final.mp4", xfade_s=0.5)
    # 3클립 합계 9초, 크로스페이드 2번 × 0.5초 = 8초. intro/outro=None 분기도 함께 덮는다.
    assert math.isclose(probe_duration(out), 8.0, abs_tol=0.3)
    streams = _stream_types(out)
    assert "video" in streams
    assert "audio" not in streams


def test_assemble_single_clip_without_ambience(tmp_path):
    """len(clips) == 1 분기([0:v]copy[v1])와 무음 분기를 함께 덮는다."""
    clip = _color_clip(tmp_path / "solo.mp4", 3, "red")
    out = assemble([clip], tmp_path / "final.mp4", xfade_s=0.5)
    assert math.isclose(probe_duration(out), 3.0, abs_tol=0.3)
    streams = _stream_types(out)
    assert "video" in streams
    assert "audio" not in streams
