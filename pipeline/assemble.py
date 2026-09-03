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


def build_sequence(loop_clips, event_clips, durations, target_s, event_every_s):
    """루프 클립을 순환하며 target_s를 채우고, event_every_s가 지날 때마다 이벤트 클립을 끼운다."""
    loop_clips, event_clips = list(loop_clips), list(event_clips)
    seq, total, since_event, i, e = [], 0.0, 0.0, 0, 0
    while total < target_s:
        clip = loop_clips[i % len(loop_clips)]
        i += 1
        seq.append(clip)
        total += durations[clip]
        since_event += durations[clip]
        if event_clips and since_event >= event_every_s and total < target_s:
            ev = event_clips[e % len(event_clips)]
            e += 1
            seq.append(ev)
            total += durations[ev]
            since_event = 0.0
    return seq


def assemble(sequence, out_path, *, intro=None, outro=None, ambience=None, xfade_s=2.0, crf=18) -> Path:
    """클립들을 xfade로 이어 붙이고 환경음을 깔아 최종 mp4를 만든다. 모든 클립은 같은 해상도·fps여야 한다."""
    clips = [Path(c) for c in ([intro] if intro else []) + list(sequence) + ([outro] if outro else [])]
    durations = [probe_duration(c) for c in clips]
    total = sum(durations) - xfade_s * (len(clips) - 1)

    # 입력(-i)은 전부 출력 옵션(-map, -t 등)보다 앞에 와야 한다.
    # -stream_loop는 바로 다음 -i에만 적용되는 입력 옵션이라 환경음 -i 직전에 둔다.
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for c in clips:
        cmd += ["-i", str(c)]
    if ambience:
        cmd += ["-stream_loop", "-1", "-i", str(ambience)]  # 스트림 인덱스 len(clips)
    filters, prev, offset = [], "[0:v]", 0.0
    for k in range(1, len(clips)):
        offset += durations[k - 1] - xfade_s
        label = f"[v{k}]"
        filters.append(f"{prev}[{k}:v]xfade=transition=fade:duration={xfade_s}:offset={offset:.3f}{label}")
        prev = label
    if len(clips) == 1:
        filters.append("[0:v]copy[v1]")
        prev = "[v1]"
    cmd += ["-filter_complex", ";".join(filters), "-map", prev]

    if ambience:
        fade_out = max(total - 3.0, 0.0)
        cmd += ["-map", f"{len(clips)}:a", "-af", f"afade=t=in:d=3,afade=t=out:st={fade_out:.3f}:d=3",
                "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
    subprocess.run(cmd, check=True)
    return out_path
