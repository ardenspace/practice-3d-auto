import json
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.layers import split_layers


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    """색이 뚜렷한 합성 이미지 + 가로 선형 그라데이션 깊이."""
    rng = np.random.default_rng(7)
    rgb = rng.integers(0, 255, (120, 200, 3), dtype=np.uint8)
    img_path = tmp_path / "src.png"
    Image.fromarray(rgb, mode="RGB").save(img_path)

    # 왼쪽 = 어두움(멂), 오른쪽 = 밝음(가까움)
    grad = np.tile(np.linspace(0, 65535, 200, dtype=np.uint16), (120, 1))
    depth_path = tmp_path / "depth.png"
    Image.fromarray(grad).save(depth_path)
    return img_path, depth_path


def test_split_layers_writes_sorted_near_first_layers(tmp_path):
    img, depth = _fixture(tmp_path)
    meta_path = split_layers(img, depth, tmp_path / "layers", n_layers=3)

    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    layers = meta["layers"]
    assert len(layers) == 3

    qmids = [layer["depth_qmid"] for layer in layers]
    assert qmids == sorted(qmids, reverse=True), f"가까운 순 정렬이 아님: {qmids}"
    assert all(0.0 <= q <= 1.0 for q in qmids)

    for layer in layers:
        assert Path(layer["png"]).exists()


def test_foreground_layer_is_rgba_with_transparent_and_opaque_pixels(tmp_path):
    img, depth = _fixture(tmp_path)
    meta = json.loads(split_layers(img, depth, tmp_path / "layers").read_text())

    fg = Image.open(meta["layers"][0]["png"])
    assert fg.mode == "RGBA"
    alpha = np.array(fg)[:, :, 3]
    assert alpha.min() == 0, "전경에 완전 투명 픽셀이 없음"
    assert alpha.max() == 255, "전경에 완전 불투명 픽셀이 없음"


def test_farthest_layer_has_no_holes(tmp_path):
    img, depth = _fixture(tmp_path)
    meta = json.loads(split_layers(img, depth, tmp_path / "layers").read_text())

    far = Image.open(meta["layers"][-1]["png"])
    if far.mode == "RGBA":
        assert np.array(far)[:, :, 3].min() == 255
    else:
        assert far.mode == "RGB"


def test_farthest_layer_fills_occluded_region_with_plausible_color(tmp_path):
    """가까운 밴드가 가리던 자리가 검은 구멍이 아니라 인페인팅으로 채워졌는지."""
    img, depth = _fixture(tmp_path)
    meta = json.loads(split_layers(img, depth, tmp_path / "layers").read_text())

    far = np.array(Image.open(meta["layers"][-1]["png"]).convert("RGB"))
    # 오른쪽 1/6(가장 가까운 밴드 안쪽)은 원경 입장에서 가려졌던 영역이다
    occluded = far[:, -far.shape[1] // 6 :]
    assert occluded.mean() > 20, "가려졌던 영역이 채워지지 않음(검은 구멍)"


def test_middle_layer_alpha_is_opaque_over_nearer_band_back_filled(tmp_path):
    """back-filled 알파: 레이어 i의 알파는 자기 밴드뿐 아니라 더 가까운 모든 밴드도 덮는다.

    이 계약이 깨지면(예: `split_layers`의 `covered = band_far_index >= far_index`를
    `== far_index`로 되돌리면) 카메라가 움직여 앞 레이어가 비켜설 때 중간 레이어의
    알파 잘린 자국이 하드 엣지로 그대로 드러난다(task-7-report.md "알파 — back-filled
    레이어" 참조). 픽스처는 가로 그라데이션 깊이(왼쪽=멂, 오른쪽=가까움)라 3밴드가
    좌→우로 원경/중경/전경이 된다.
    """
    img, depth = _fixture(tmp_path)
    meta = json.loads(
        split_layers(img, depth, tmp_path / "layers", n_layers=3).read_text()
    )

    mid = Image.open(meta["layers"][1]["png"])  # 중경(index 1)
    assert mid.mode == "RGBA"
    alpha = np.array(mid)[:, :, 3]

    # 오른쪽 끝은 전경(레이어 0)의 밴드 — 중경 레이어 "자기 밴드" 밖이다.
    width = alpha.shape[1]
    foreground_band_column = alpha[:, int(width * 0.95)]
    assert foreground_band_column.min() == 255, (
        "중경 레이어의 알파가 더 가까운 밴드(전경)에서 불투명하지 않음"
        " — back-filled 알파 계약 위반"
    )


def _two_tone_fixture(tmp_path: Path) -> tuple[Path, Path, np.ndarray, np.ndarray]:
    """왼쪽 절반=배경색(파랑), 오른쪽 절반=전경색(빨강), 가로 선형 그라데이션 깊이.

    depth가 왼쪽(멂)→오른쪽(가까움)으로 단조 증가하므로 n_layers=2에서 밴드 경계가
    색 경계와 거의 겹친다. 전경 레이어(index 0)의 페더 링은 원래 배경 영역(왼쪽) 쪽으로
    몇 px 번지므로, 링 RGB가 배경색 사본인지 전경색으로 확장됐는지를 색 거리로 판별할 수 있다.
    """
    height, width = 60, 200
    bg_color = np.array([30, 30, 200], dtype=np.uint8)  # 배경 = 파랑
    fg_color = np.array([200, 30, 30], dtype=np.uint8)  # 전경 = 빨강

    rgb = np.empty((height, width, 3), dtype=np.uint8)
    rgb[:, : width // 2] = bg_color
    rgb[:, width // 2 :] = fg_color
    img_path = tmp_path / "src_two_tone.png"
    Image.fromarray(rgb, mode="RGB").save(img_path)

    grad = np.tile(np.linspace(0, 65535, width, dtype=np.uint16), (height, 1))
    depth_path = tmp_path / "depth_two_tone.png"
    Image.fromarray(grad).save(depth_path)
    return img_path, depth_path, bg_color, fg_color


def test_foreground_feather_ring_color_extends_from_layer_not_background(tmp_path):
    """페더 링(0<α<255)의 RGB가 배경 픽셀 사본이 아니라 전경 레이어 자신의 색으로 확장돼야 한다.

    회귀 시나리오: 링이 배경 픽셀 사본이면 카메라가 움직일 때 레이어가 배경 조각을
    유령처럼 끌고 다닌다(레이어 인페인팅 품질 개선 브리프 참조). 이 테스트는 링 RGB가
    배경색보다 전경 밴드 색에 (평균적으로) 더 가까워야 한다고 단언한다.
    """
    img, depth, bg_color, fg_color = _two_tone_fixture(tmp_path)
    meta = json.loads(
        split_layers(img, depth, tmp_path / "layers", n_layers=2).read_text()
    )

    fg = Image.open(meta["layers"][0]["png"])
    assert fg.mode == "RGBA"
    arr = np.array(fg)
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3].astype(np.float32)

    ring = (alpha > 0) & (alpha < 255)
    assert ring.any(), "페더 링(부분 투명) 픽셀이 없음 — 픽스처를 확인"

    ring_rgb = rgb[ring]
    dist_to_bg = np.linalg.norm(ring_rgb - bg_color.astype(np.float32), axis=1)
    dist_to_fg = np.linalg.norm(ring_rgb - fg_color.astype(np.float32), axis=1)
    assert dist_to_fg.mean() < dist_to_bg.mean(), (
        "페더 링 RGB가 배경색 사본에 가깝다 — 유령 윤곽 회귀"
        f" (평균 거리: 전경 {dist_to_fg.mean():.1f}, 배경 {dist_to_bg.mean():.1f})"
    )


def test_layer_pngs_keep_source_resolution(tmp_path):
    img, depth = _fixture(tmp_path)
    meta = json.loads(split_layers(img, depth, tmp_path / "layers").read_text())
    for layer in meta["layers"]:
        assert Image.open(layer["png"]).size == (200, 120)
