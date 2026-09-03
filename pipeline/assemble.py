"""ffmpeg 조립: 클립 길이 조회, 반복, 교차 배열 롱폼 생성."""

import json
import subprocess
from pathlib import Path


def probe_duration(path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(proc.stdout)["format"]["duration"])


def repeat_clip(clip, out_path, times=2) -> Path:
    """클립을 times번 이어 붙인다(재인코딩 없음). 루프 이음새를 눈으로 확인하는 용도."""
    out_path = Path(out_path)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(times - 1),
                    "-i", str(clip), "-c", "copy", str(out_path)], check=True)
    return out_path
