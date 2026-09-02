"""단일 이미지 깊이 추출 모듈.

모델 교체(Marigold, Depth Pro 등)에 대비해 깊이 추출은 이 모듈 뒤에 숨긴다.
호출자는 extract_depth()의 계약(같은 해상도, 16비트 PNG, 밝음=가까움)만 의존한다.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
_pipe = None


def _get_pipe():
    global _pipe
    if _pipe is None:
        from transformers import pipeline as hf_pipeline

        _pipe = hf_pipeline("depth-estimation", model=MODEL_ID)
    return _pipe


def extract_depth(image_path: Path, out_path: Path) -> Path:
    image = Image.open(image_path).convert("RGB")
    depth = np.array(_get_pipe()(image)["depth"], dtype=np.float32)

    lo, hi = float(depth.min()), float(depth.max())
    norm = (depth - lo) / (hi - lo) if hi > lo else np.zeros_like(depth)

    depth_16bit = Image.fromarray((norm * 65535.0).astype(np.uint16))
    if depth_16bit.size != image.size:
        depth_16bit = depth_16bit.resize(image.size, Image.BILINEAR)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    depth_16bit.save(out_path)
    return out_path


if __name__ == "__main__":
    extract_depth(Path(sys.argv[1]), Path(sys.argv[2]))
