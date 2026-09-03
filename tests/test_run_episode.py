import json
import subprocess

from pipeline.assemble import probe_duration
from pipeline.run_episode import run


def test_run_episode_end_to_end_tiny(tmp_path):
    ep = tmp_path / "tiny"
    ep.mkdir()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=110:duration=1",
                    str(ep / "amb.wav")], check=True)
    (ep / "shots.json").write_text(json.dumps({
        "scene": "bus_stop",
        "resolution": [160, 90], "fps": 12, "samples": 4,
        "target_minutes": 0.1, "event_every_s": 2.0, "xfade_s": 0.25,
        "ambience": str(ep / "amb.wav"),
        "intro": {"scene": "planet", "camera": "main", "event": "descend", "duration_s": 1},
        "outro": {"scene": "planet", "camera": "main", "event": "ascend", "duration_s": 1},
        "loops": [{"camera": "wide", "duration_s": 1}, {"camera": "marble", "duration_s": 1}],
        "events": [{"camera": "wide", "event": "bus", "duration_s": 1}],
    }))
    out = run(ep)
    assert out.exists()
    assert probe_duration(out) >= 6.0 - 0.5  # 목표 6초 이상을 채우고 크로스페이드로 조금 줄어든다
    # 재실행하면 렌더를 건너뛰고 같은 결과를 낸다
    mtimes = {p: p.stat().st_mtime for p in (ep / "renders").glob("*.mp4")}
    run(ep)
    assert {p: p.stat().st_mtime for p in (ep / "renders").glob("*.mp4")} == mtimes
