"""회차 정의(shots.json)를 읽어 클립을 전부 렌더하고 롱폼을 조립한다. 재실행 안전."""

import json
import sys
from pathlib import Path

from pipeline.assemble import assemble, build_sequence, probe_duration
from pipeline.config import PROJECT_ROOT
from pipeline.render_shot import render_clip


def _render(shot, spec, renders, default_scene):
    """클립 파일명 규칙: <scene>_<camera>_<event>.mp4. 이미 있으면 render_clip이 건너뛴다."""
    scene = shot.get("scene", default_scene)
    frames = int(shot["duration_s"] * spec["fps"])
    out = renders / f"{scene}_{shot['camera']}_{shot.get('event', 'none')}.mp4"
    return render_clip(scene, shot["camera"], out, frame_start=1, frame_end=frames,
                       resolution=tuple(spec["resolution"]), fps=spec["fps"], samples=spec["samples"],
                       event=shot.get("event", "none"))


def run(episode_dir) -> Path:
    episode_dir = Path(episode_dir)
    spec = json.loads((episode_dir / "shots.json").read_text())
    renders = episode_dir / "renders"
    renders.mkdir(exist_ok=True)

    loops = [_render(s, spec, renders, spec["scene"]) for s in spec["loops"]]
    events = [_render(s, spec, renders, spec["scene"]) for s in spec.get("events", [])]
    intro = _render(spec["intro"], spec, renders, spec["scene"]) if spec.get("intro") else None
    outro = _render(spec["outro"], spec, renders, spec["scene"]) if spec.get("outro") else None

    durations = {c: probe_duration(c) for c in loops + events}
    sequence = build_sequence(loops, events, durations, spec["target_minutes"] * 60.0, spec["event_every_s"])

    ambience = spec.get("ambience")
    if ambience:
        ambience = Path(ambience) if Path(ambience).is_absolute() else PROJECT_ROOT / ambience
        if not ambience.exists():
            raise FileNotFoundError(f"환경음 파일이 없습니다: {ambience}")

    minutes = spec["target_minutes"]
    label = f"{minutes:g}min"
    out = episode_dir / "final" / f"{episode_dir.name}_{label}.mp4"
    return assemble(sequence, out, intro=intro, outro=outro, ambience=ambience, xfade_s=spec["xfade_s"])


if __name__ == "__main__":
    print(run(sys.argv[1]))
