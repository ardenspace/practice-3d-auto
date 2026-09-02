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
