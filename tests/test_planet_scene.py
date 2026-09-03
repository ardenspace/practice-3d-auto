from PIL import Image

from pipeline.render_shot import check_scene, render_clip


def test_planet_scene_objects():
    info = check_scene("planet", camera="main", event="descend", frame_end=8)
    assert "planet" in info["objects"] and "main" in info["cameras"]
    assert sum(n.startswith("star_") for n in info["objects"]) >= 200
    assert sum(n.startswith("city_") for n in info["objects"]) >= 8


def test_descend_and_ascend_both_render(tmp_path):
    for event in ("descend", "ascend"):
        out = render_clip("planet", "main", tmp_path / f"{event}.png", frame_start=1, frame_end=8,
                          resolution=(160, 90), samples=4, still=True, event=event)
        img = Image.open(out).convert("L")
        assert 1 < sum(img.get_flattened_data()) / (160 * 90) < 120
