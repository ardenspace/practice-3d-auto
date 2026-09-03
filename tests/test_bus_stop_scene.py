from PIL import Image

from pipeline.render_shot import check_scene, render_clip


def test_bus_stop_has_no_bus_without_event():
    info = check_scene("bus_stop", camera="wide", event="none")
    assert not any(n.startswith("bus_") for n in info["objects"])
    assert info["extra"]["camera"] == "wide"


def test_bus_stop_frame_range_is_respected():
    info = check_scene("bus_stop", camera="puddle", frame_end=12)
    assert info["frame_start"] == 1 and info["frame_end"] == 12


def test_bus_stop_lights_exist():
    info = check_scene("bus_stop", camera="wide")
    assert {"lamp_spot", "lamp_fill", "moon"} <= set(info["lights"])
    assert "rain_emitter" in info["objects"]


def test_wide_still_is_lit_but_not_blown_out(tmp_path):
    out = render_clip("bus_stop", "wide", tmp_path / "wide.png", resolution=(320, 180), samples=8, still=True)
    img = Image.open(out).convert("L")
    mean = sum(img.getdata()) / (320 * 180)
    assert 3 < mean < 140, mean  # 밤 장면: 검지 않되 어둡다


def test_bus_stop_new_props_are_present():
    """관문 1 반복 중 추가한 소품 대표 몇 개가 실제로 지어지는지 확인한다."""
    info = check_scene("bus_stop", camera="wide")
    objs = set(info["objects"])
    for name in (
        "curb", "drain_frame", "bollard_0", "bollard_1",
        "shelter_side_l", "shelter_side_r", "timetable_bezel", "timetable_panel",
        "bench_slat_front", "bench_seat", "bench_slat_back", "bench_backrest",
        "lean_rail", "roof_gutter_front", "roof_gutter_back",
        "bin_lid", "bin_groove_0", "lamp_post_base", "sign_pole_base", "sign_bracket",
        "power_wire_0", "power_wire_1", "tree0_branch_0", "tree0_canopy_1", "leaf_0",
    ):
        assert name in objs, name


def test_bus_stop_scene_is_deterministic():
    """같은 시드로 두 번 지으면(나무 가지·캐노피, 낙엽 배치가 random을 쓰므로) 오브젝트 목록이 같아야 한다."""
    first = check_scene("bus_stop", camera="wide")
    second = check_scene("bus_stop", camera="wide")
    assert first["objects"] == second["objects"]
