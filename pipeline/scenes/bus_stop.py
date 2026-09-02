"""꿈에서 본 듯한 정류장. 기본 도형만으로 짓는다.

호출은 파일 상단 CLI 계약(docs/superpowers/plans/2026-09-02-nameless-city-first-episode.md) 참조.
좌표계: 도로는 X축을 따라 놓이고(y=0 중심, 폭 7m), 인도와 정류장은 +y 쪽이다. 단위는 m.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import common  # noqa: E402
import motion  # noqa: E402

PARAMS = {
    "palette": {
        "night": (0.010, 0.015, 0.030),   # 하늘·배경
        "asphalt": (0.030, 0.033, 0.040),
        "concrete": (0.070, 0.072, 0.080),
        "steel": (0.120, 0.125, 0.140),
        "wood": (0.240, 0.150, 0.080),
        "amber": (1.000, 0.620, 0.300),   # 가로등
        "fog": (0.550, 0.650, 0.800),
        "moon": (0.550, 0.650, 1.000),
    },
    "fog": {"density": 0.025, "emission_strength": 0.004, "emission": (0.35, 0.45, 0.65), "end": 80.0, "samples": 64},
    "lamp": {"energy": 2500.0, "fill_energy": 150.0, "spot_size_deg": 120.0, "blend": 0.6, "head_emission": 40.0,
             "flicker_dips": [(0.31, 0.004, 0.55), (0.33, 0.003, 0.35), (0.72, 0.005, 0.45)]},
    "moon": {"energy": 0.08, "rotation_deg": (50.0, 0.0, -30.0)},
    "glare": {"glare_threshold": 1.0, "glare_strength": 0.25, "glare_size": 0.6},
    "rain": {"count": 4000, "lifetime": 40, "emitter_z": 9.0, "emitter_size": 40.0, "seed": 7},
    "cameras": {
        "wide":    {"location": (-1.0, -9.0, 1.6), "target": (0.5, 4.5, 1.3), "lens": 32, "fstop": 2.8,
                    "amplitudes": (0.6, 0.0, 0.08), "harmonics": (1, 1, 2)},
        "shelter": {"location": (-1.2, 5.3, 1.5), "target": (30.0, 2.0, 1.2), "lens": 35, "fstop": 2.0,
                    "amplitudes": (0.4, 0.0, 0.03), "harmonics": (1, 1, 2)},
        "marble":  {"location": (0.9, 4.2, 1.15), "target": (0.3, 5.0, 0.95), "lens": 60, "fstop": 1.4,
                    "amplitudes": (0.12, 0.08, 0.02), "harmonics": (1, 1, 1)},
        "puddle":  {"location": (1.5, -2.0, 0.25), "target": (2.5, 4.3, 1.0), "lens": 28, "fstop": 2.8,
                    "amplitudes": (0.0, 0.0, 0.15), "harmonics": (1, 1, 1)},
    },
    "bus": {"x_start": -70.0, "x_end": 70.0, "y": 1.8, "headlight_energy": 3000.0},
}


def build_ground_and_road(p):
    pal = p["palette"]
    common.add_plane("ground", 200.0, (0, 0, 0), common.make_material("ground", pal["night"], roughness=0.5))
    common.add_box("road", (120.0, 7.0, 0.10), (0, 0, 0.05), common.make_material("asphalt", pal["asphalt"], roughness=0.25), bevel=0.0)
    common.add_box("sidewalk", (30.0, 3.5, 0.25), (0, 5.25, 0.125), common.make_material("concrete", pal["concrete"], roughness=0.35), bevel=0.02)
    # 도로 가운데 점선
    dash = common.make_material("dash", (0.35, 0.33, 0.25), roughness=0.5)
    for i in range(-14, 15):
        common.add_box(f"dash_{i}", (2.0, 0.12, 0.01), (i * 4.0, 0, 0.105), dash, bevel=0.0)


def build_shelter(p):
    pal = p["palette"]
    steel = common.make_material("steel", pal["steel"], roughness=0.4, metallic=0.3)
    glass = common.make_material("glass", (0.6, 0.7, 0.8), roughness=0.05, alpha=0.18)
    for name, (x, y) in {"post_fl": (-1.5, 4.3), "post_fr": (1.5, 4.3), "post_bl": (-1.5, 5.9), "post_br": (1.5, 5.9)}.items():
        common.add_box(name, (0.08, 0.08, 2.6), (x, y, 1.3), steel, bevel=0.01)
    common.add_box("shelter_roof", (3.4, 1.8, 0.06), (0, 5.1, 2.63), glass, bevel=0.01)
    common.add_box("shelter_back", (3.0, 0.03, 2.2), (0, 5.9, 1.35), glass, bevel=0.0)
    wood = common.make_material("wood", pal["wood"], roughness=0.6)
    common.add_box("bench_seat", (2.0, 0.42, 0.06), (0, 5.0, 0.50), wood, bevel=0.01)
    for name, x in (("bench_leg_l", -0.8), ("bench_leg_r", 0.8)):
        common.add_box(name, (0.06, 0.38, 0.45), (x, 5.0, 0.24), steel, bevel=0.005)


def build_lamp_and_props(p):
    pal = p["palette"]
    steel = bpy.data.materials["steel"]
    common.add_cylinder("lamp_post", 0.06, 4.4, (3.5, 4.2, 2.2), steel)
    head = common.make_material("lamp_head", pal["amber"], emission=pal["amber"], emission_strength=p["lamp"]["head_emission"])
    common.add_sphere("lamp_head", 0.18, (3.5, 4.2, 4.5), head)
    # 노선 표지판: 기둥 + 판. 글자는 읽을 수 없는 기호 대신 얇은 막대 세 개
    common.add_cylinder("sign_pole", 0.03, 2.4, (-2.5, 4.1, 1.2), steel)
    common.add_box("sign_board", (0.5, 0.03, 0.7), (-2.5, 4.1, 2.2), common.make_material("sign", (0.08, 0.10, 0.14), roughness=0.5), bevel=0.01)
    glyph = common.make_material("glyph", (0.75, 0.72, 0.60), roughness=0.6)
    for i, w in enumerate((0.30, 0.18, 0.26)):
        common.add_box(f"glyph_{i}", (w, 0.01, 0.04), (-2.5 - (0.30 - w) / 2, 4.08, 2.38 - i * 0.14), glyph, bevel=0.0)
    common.add_cylinder("bin", 0.22, 0.75, (2.2, 4.3, 0.375 + 0.25), common.make_material("bin", (0.05, 0.06, 0.07), roughness=0.5), bevel=0.02)
    # 유리구슬: 벤치 위. 안에 아주 작은 행성
    marble = common.make_material("marble", (0.9, 0.95, 1.0), roughness=0.0, transmission=1.0, ior=1.5)
    common.add_sphere("marble_glass", 0.08, (0.3, 5.0, 0.53 + 0.08), marble)
    common.add_sphere("marble_core", 0.025, (0.3, 5.0, 0.61),
                      common.make_material("marble_core", (0.2, 0.3, 0.6), emission=(0.4, 0.6, 1.0), emission_strength=3.0))


def build_background(p):
    pal = p["palette"]
    dark = common.make_material("silhouette", (0.012, 0.014, 0.020), roughness=0.9)
    for i, (x, y, h) in enumerate(((-9, 9, 7), (-4, 12, 9), (6, 11, 8), (12, 9, 6.5))):
        common.add_cylinder(f"trunk_{i}", 0.12, h, (x, y, h / 2), dark)
        for j, (r, z) in enumerate(((1.4, h * 0.55), (1.1, h * 0.75), (0.7, h * 0.92))):
            common.add_sphere(f"canopy_{i}_{j}", r, (x, y, z), dark)
    for i, x in enumerate((-14.0, 14.0)):
        common.add_cylinder(f"pole_{i}", 0.10, 7.0, (x, 6.5, 3.5), dark)
        common.add_box(f"crossbar_{i}", (1.6, 0.08, 0.08), (x, 6.5, 6.6), dark, bevel=0.0)
    # 멀리 보이는 다른 정류장의 불빛
    far = common.make_material("far_light", pal["amber"], emission=pal["amber"], emission_strength=20.0)
    common.add_sphere("far_light", 0.12, (55.0, 6.0, 3.0), far)


def build_puddles(p):
    water = common.make_material("water", (0.010, 0.012, 0.018), roughness=0.03)
    for i, (x, y, r) in enumerate(((1.0, -1.5, 1.6), (-3.0, 2.2, 1.1), (2.6, 3.9, 0.7))):
        common.add_cylinder(f"puddle_{i}", r, 0.006, (x, y, 0.103 if y < 3.5 else 0.253), water, vertices=48)


def build_cameras(p, frame_start, frame_end):
    cams = {}
    marble = bpy.data.objects["marble_glass"]
    for name, c in p["cameras"].items():
        cam = common.add_camera(name, c["location"], c["target"], lens=c["lens"], fstop=c["fstop"],
                                focus_target=marble if name == "marble" else None)
        common.keyframe_loop_motion(cam, c["location"], c["amplitudes"], frame_start, frame_end, c["harmonics"])
        cams[name] = cam
    return cams


def build(params, frame_start, frame_end, event):
    build_ground_and_road(params)
    build_shelter(params)
    build_lamp_and_props(params)
    build_background(params)
    build_puddles(params)
    return build_cameras(params, frame_start, frame_end)


if __name__ == "__main__":
    common.run_scene(build, PARAMS)
