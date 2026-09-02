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


def test_layer_pngs_keep_source_resolution(tmp_path):
    img, depth = _fixture(tmp_path)
    meta = json.loads(split_layers(img, depth, tmp_path / "layers").read_text())
    for layer in meta["layers"]:
        assert Image.open(layer["png"]).size == (200, 120)
