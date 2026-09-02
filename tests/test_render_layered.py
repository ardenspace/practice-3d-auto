"""layered 모드 스모크: 레이어 정합 · 레이어 간 시차 · 풀 렌더."""

import json
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.render import render_shot

SRC_W, SRC_H = 480, 270
RES = [320, 180]


def _write_spec(tmp_path: Path, name: str, amplitude: float, **overrides) -> Path:
    spec = {
        "image": str(tmp_path / "src.png"),
        "depth": str(tmp_path / "depth.png"),
        "out_dir": str(tmp_path / "renders"),
        "name": name,
        "mode": "layered",
        "n_layers": 3,
        "resolution": RES,
        "fps": 12,
        "duration_s": 1,
        "depth_strength": 0.3,
        "camera": {"move": "push_in", "amplitude": amplitude, "sway": 0.0, "loop": False},
        "fog_density": 0.0,
    }
    spec.update(overrides)
    spec_path = tmp_path / f"{name}.json"
    spec_path.write_text(json.dumps(spec))
    return spec_path


def _vertical_depth(tmp_path: Path) -> None:
    """세로 그라데이션 깊이: 아래쪽이 밝음 = 가까움. 밴드가 가로로 3등분된다."""
    grad = np.tile(
        np.linspace(0, 65535, SRC_H, dtype=np.uint16).reshape(-1, 1), (1, SRC_W)
    )
    Image.fromarray(grad).save(tmp_path / "depth.png")


def test_layers_composite_like_source_at_start(tmp_path):
    """카메라 시작 위치에서 세 레이어가 원본과 동일하게 겹쳐 보이는지.

    가로 그라데이션 깊이로 밴드를 세로 3등분하고, 원본에는 가로 경계선을 그린다.
    레이어 배치가 어긋나면 밴드마다 경계선의 높이가 달라진다. 경계선을 화면 중앙에
    두면 배율이 틀려도 중앙은 그대로라 어긋남이 안 잡히므로 위쪽 30% 지점에 둔다.
    """
    boundary_ratio = 0.30
    rgb = np.zeros((SRC_H, SRC_W, 3), np.uint8)
    rgb[int(SRC_H * boundary_ratio) :] = 255  # 위 검정 / 아래 흰색
    Image.fromarray(rgb).save(tmp_path / "src.png")
    grad = np.tile(np.linspace(0, 65535, SRC_W, dtype=np.uint16), (SRC_H, 1))
    Image.fromarray(grad).save(tmp_path / "depth.png")

    out = render_shot(_write_spec(tmp_path, "align", 0.0), "preview")
    frame = np.array(Image.open(out).convert("L"), dtype=np.float32)
    assert frame.shape == (RES[1], RES[0])

    third = RES[0] // 3
    boundaries = []
    for band in range(3):
        column_mean = frame[:, band * third : (band + 1) * third].mean(axis=1)
        bright = np.nonzero(column_mean > column_mean.max() / 2)[0]
        assert bright.size, f"밴드 {band}에 밝은 영역이 없음"
        boundaries.append(int(bright[0]))

    assert max(boundaries) - min(boundaries) <= 2, f"밴드별 경계 높이 불일치: {boundaries}"
    # 평면 여백(PLANE_MARGIN) 때문에 원본이 살짝 확대돼 보인다: 중앙에서 위로 0.2×1.08
    expected = RES[1] * (0.5 - (0.5 - boundary_ratio) * 1.08)
    assert abs(boundaries[1] - expected) <= 3, (
        f"경계 위치가 기대({expected:.0f})와 다름: {boundaries}"
    )


def test_push_in_magnifies_near_layer_more_than_far_layer(tmp_path):
    """레이어 간 실제 시차 확인 — 관문 1이 "이미지 확대"로 미달했던 지점.

    가까운 밴드와 먼 밴드에 같은 크기의 사각형을 하나씩 두고 푸시인 전후 면적을 잰다.
    단일 평면이라면 두 사각형이 같은 비율로 커지고, 레이어가 분리돼 있어야 가까운
    사각형이 더 크게 커진다.
    """
    _vertical_depth(tmp_path)
    rgb = np.zeros((SRC_H, SRC_W, 3), np.uint8)
    half = int(0.04 * SRC_H)
    for center_y in (int(0.22 * SRC_H), int(0.78 * SRC_H)):
        rgb[center_y - half : center_y + half, SRC_W // 2 - half : SRC_W // 2 + half] = 255
    Image.fromarray(rgb).save(tmp_path / "src.png")

    def bright_areas(name: str, amplitude: float) -> tuple[int, int]:
        out = render_shot(_write_spec(tmp_path, name, amplitude), "preview")
        frame = np.array(Image.open(out).convert("L"))
        mid = RES[1] // 2
        return int((frame[:mid] > 128).sum()), int((frame[mid:] > 128).sum())

    far_before, near_before = bright_areas("still", 0.0)
    far_after, near_after = bright_areas("pushed", 0.6)

    assert min(far_before, near_before) > 20, "기준 프레임에 사각형이 보이지 않음"
    near_growth = near_after / near_before
    far_growth = far_after / far_before
    assert near_growth > far_growth * 1.15, (
        f"레이어 간 시차가 없음: 근경 {near_growth:.2f}배 vs 원경 {far_growth:.2f}배"
    )


def test_layered_full_render_writes_mp4(tmp_path):
    rng = np.random.default_rng(3)
    Image.fromarray(rng.integers(0, 255, (SRC_H, SRC_W, 3), dtype=np.uint8)).save(
        tmp_path / "src.png"
    )
    _vertical_depth(tmp_path)

    spec_path = _write_spec(tmp_path, "layered_full", 0.6, duration_s=2, fog_density=0.05)
    out = render_shot(spec_path, "full")
    assert out.exists() and out.suffix == ".mp4"
    assert out.stat().st_size > 10_000


def test_render_shot_reuses_existing_layer_artifacts(tmp_path):
    """레이어 산출물은 한 번만 만들고 재사용한다(렌더 반복 시 재계산 금지)."""
    from pipeline.layers import layers_json_path
    from pipeline.render import _prepare_layers

    rng = np.random.default_rng(4)
    Image.fromarray(rng.integers(0, 255, (SRC_H, SRC_W, 3), dtype=np.uint8)).save(
        tmp_path / "src.png"
    )
    _vertical_depth(tmp_path)
    spec = json.loads(_write_spec(tmp_path, "reuse", 0.6).read_text())

    meta_path = _prepare_layers(spec)
    assert meta_path == layers_json_path(tmp_path / "src.png", 3)
    stamp = meta_path.stat().st_mtime_ns
    assert _prepare_layers(spec).stat().st_mtime_ns == stamp
