from pathlib import Path

from pipeline.config import BLENDER_BIN, PROJECT_ROOT


def test_project_root_is_repo_root():
    assert (PROJECT_ROOT / "pipeline").is_dir()


def test_blender_bin_exists():
    assert Path(BLENDER_BIN).exists(), f"Blender 실행 파일이 없습니다: {BLENDER_BIN}"
