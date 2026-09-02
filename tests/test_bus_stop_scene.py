from pipeline.render_shot import check_scene


def test_bus_stop_has_no_bus_without_event():
    info = check_scene("bus_stop", camera="wide", event="none")
    assert not any(n.startswith("bus_") for n in info["objects"])
    assert info["extra"]["camera"] == "wide"


def test_bus_stop_frame_range_is_respected():
    info = check_scene("bus_stop", camera="puddle", frame_end=12)
    assert info["frame_start"] == 1 and info["frame_end"] == 12
