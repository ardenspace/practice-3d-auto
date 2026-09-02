"""깊이 밴드 분리: 이미지 1장 + 깊이맵 → 겹쳐 놓으면 원본이 되는 레이어 PNG 묶음.

단일 평면 부조(relief)는 카메라가 다가가도 "이미지 확대"로 보인다. 레이어 간
실제 시차를 만들려면 장면을 깊이 밴드로 쪼개 서로 다른 거리의 평면에 올려야 한다.

산출물 계약:
- `layers.json`: `{"layers": [{"png": ..., "depth_qmid": ...}, ...]}`, 가까운 레이어가 먼저.
- 전경·중경 레이어는 RGBA(밴드 밖은 투명), 최원경 레이어는 구멍 없는 RGB.
- 모든 레이어 PNG는 원본과 같은 해상도다(Blender 쪽 기하가 이를 전제한다).

이 모듈은 venv 쪽(numpy/PIL/cv2)에서만 돈다. Blender 안에서는 import되지 않는다.
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

INPAINT_RADIUS = 8  # cv2.inpaint(TELEA) 반경(px)
INPAINT_SCALE = 0.25  # 인페인팅을 수행하는 축소 배율(아래 _fill_occlusions 주석 참조)
FEATHER_RATIO = 0.004  # 이미지 긴 변 대비 페더/디레이트 폭
FEATHER_MIN_PX = 2


def layers_json_path(image_path: Path, n_layers: int) -> Path:
    """샷 스펙의 image 경로에서 레이어 산출물 위치를 유도한다.

    Blender 쪽 스크립트(pipeline/blender/parallax_scene.py)가 이 규칙을 그대로
    복제해서 같은 경로를 찾는다. 프로세스 경계 때문에 import를 공유할 수 없으므로
    규칙을 바꾸면 양쪽을 함께 고쳐야 한다(shot_spec.md에 명시).
    """
    image_path = Path(image_path)
    return image_path.parent / f"{image_path.stem}_layers{n_layers}" / "layers.json"


def _band_thresholds(depth: np.ndarray, n_layers: int) -> np.ndarray:
    """분위수 경계. 깊이가 단조롭지 않아 분위수가 겹치면 균등 분할로 대체한다."""
    qs = np.linspace(0.0, 1.0, n_layers + 1)[1:-1]
    thresholds = np.quantile(depth, qs)
    if thresholds.size and not np.all(np.diff(thresholds) > 0):
        thresholds = np.linspace(depth.min(), depth.max(), n_layers + 1)[1:-1]
    return thresholds


def _feather_px(shape: tuple[int, int]) -> int:
    return max(FEATHER_MIN_PX, int(round(FEATHER_RATIO * max(shape))))


def _soft_alpha(hard_mask: np.ndarray, feather: int) -> np.ndarray:
    """커버리지 마스크를 몇 px 넓힌 뒤 경계를 흐려 알파 그라데이션을 만든다."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * feather + 1,) * 2)
    grown = cv2.dilate(hard_mask.astype(np.uint8) * 255, kernel)
    ksize = 2 * feather + 1
    return cv2.GaussianBlur(grown, (ksize, ksize), 0)


def _fill_occlusions(rgb: np.ndarray, hole_mask: np.ndarray, feather: int) -> np.ndarray:
    """더 가까운 밴드가 가리던 영역을 인페인팅으로 채우고 이음매를 살짝 흐린다.

    원본 해상도에서 바로 TELEA를 돌리면 전경이 차지하던 큰 구멍이 경계 색을 길게
    끌어당긴 흰 줄무늬로 메워진다(파일럿 이미지에서 확인). 축소본에서 채우면 같은
    반경이 상대적으로 훨씬 넓게 퍼져 매끈한 배경 색조로 메워지고, 다시 키우면서
    자연스럽게 흐려져 초점이 나간 배경처럼 보인다. 드러나는 자리는 어차피 원본에
    없던 정보이므로 구조를 지어내기보다 부드럽게 뭉개는 편이 덜 튄다.
    """
    if not hole_mask.any():
        return rgb

    height, width = rgb.shape[:2]
    small_size = (
        max(8, int(width * INPAINT_SCALE)),
        max(8, int(height * INPAINT_SCALE)),
    )
    small = cv2.resize(rgb, small_size, interpolation=cv2.INTER_AREA)
    small_mask = cv2.resize(
        hole_mask.astype(np.uint8) * 255, small_size, interpolation=cv2.INTER_NEAREST
    )
    small_mask = cv2.dilate(small_mask, np.ones((3, 3), np.uint8))
    filled_small = cv2.inpaint(small, small_mask, INPAINT_RADIUS, cv2.INPAINT_TELEA)
    filled = cv2.resize(filled_small, (width, height), interpolation=cv2.INTER_LINEAR)

    # 구멍 안쪽은 채운 값, 바깥은 원본. 경계는 페더 폭만큼 부드럽게 섞는다.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * feather + 1,) * 2)
    grown = cv2.dilate(hole_mask.astype(np.uint8) * 255, kernel)
    ksize = 2 * feather + 1
    weight = (cv2.GaussianBlur(grown, (ksize, ksize), 0).astype(np.float32) / 255.0)[
        :, :, None
    ]
    return (rgb * (1.0 - weight) + filled * weight).astype(np.uint8)


def split_layers(
    image_path: Path, depth_path: Path, out_dir: Path, n_layers: int = 3
) -> Path:
    """깊이 분위수로 이미지를 n_layers장의 레이어 PNG로 쪼개고 메타 JSON을 쓴다."""
    if n_layers < 2:
        raise ValueError(f"n_layers는 2 이상이어야 합니다: {n_layers}")

    rgb = np.array(Image.open(image_path).convert("RGB"), dtype=np.uint8)
    depth_img = Image.open(depth_path)
    if depth_img.size != (rgb.shape[1], rgb.shape[0]):
        depth_img = depth_img.resize((rgb.shape[1], rgb.shape[0]), Image.BILINEAR)
    depth = np.asarray(depth_img, dtype=np.float32)
    lo, hi = float(depth.min()), float(depth.max())
    depth = (depth - lo) / (hi - lo) if hi > lo else np.zeros_like(depth)

    thresholds = _band_thresholds(depth, n_layers)
    # band_far_index: 0 = 가장 먼 밴드 … n-1 = 가장 가까운 밴드
    band_far_index = np.digitize(depth, thresholds)
    feather = _feather_px(rgb.shape[:2])

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    edges = np.concatenate(([0.0], thresholds, [1.0]))
    layers = []
    for near_index in range(n_layers):  # 0 = 가장 가까운 레이어(가까운 순 출력)
        far_index = n_layers - 1 - near_index
        band = band_far_index == far_index

        if band.any():
            qmid = float(np.median(depth[band]))
        else:  # 밴드가 비면 경계 중앙값으로 대체해 레이어 수를 유지한다
            qmid = float((edges[far_index] + edges[far_index + 1]) / 2)

        occluded = band_far_index > far_index  # 더 가까운 밴드가 가리던 자리
        content = _fill_occlusions(rgb, occluded, feather)  # rgb를 변경하지 않는다

        # 알파는 자기 밴드뿐 아니라 "더 가까운 밴드"까지 덮는다(back-filled 레이어).
        # 시작 프레임에서는 더 가까운 레이어가 그 영역을 불투명하게 덮으므로 합성 결과가
        # 같고, 카메라가 움직여 앞 레이어가 비켜서면 최원경의 뭉갠 배경이 아니라 바로
        # 뒤 레이어의 인페인팅 결과가 드러난다. 밴드만 덮으면 알파 잘린 자국이 그대로
        # 보인다(파일럿 이미지에서 확인).
        covered = band_far_index >= far_index

        is_farthest = near_index == n_layers - 1
        if is_farthest:
            # 최원경은 화면 전체를 구멍 없이 덮는다(알파 불필요)
            layer_img = Image.fromarray(content, mode="RGB")
        else:
            alpha = _soft_alpha(covered, feather)
            layer_img = Image.fromarray(
                np.dstack([content, alpha]).astype(np.uint8), mode="RGBA"
            )

        png_path = out_dir / f"layer{near_index}.png"
        layer_img.save(png_path)
        layers.append({"png": str(png_path.resolve()), "depth_qmid": qmid})

    meta_path = out_dir / "layers.json"
    meta_path.write_text(json.dumps({"layers": layers}, indent=2))
    return meta_path


if __name__ == "__main__":
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    print(split_layers(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), n))
