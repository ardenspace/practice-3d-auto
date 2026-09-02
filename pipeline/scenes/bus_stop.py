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
        "night": (0.010, 0.015, 0.030),   # 지면 알베도
        "sky": (0.0016, 0.0022, 0.0045),  # 월드 배경. AgX 가 어두운 값을 크게 들어 올리므로 지면 알베도보다 훨씬 낮다
        "asphalt": (0.042, 0.045, 0.055),
        "concrete": (0.105, 0.108, 0.118),
        "steel": (0.120, 0.125, 0.140),
        "wood": (0.240, 0.150, 0.080),
        "amber": (1.000, 0.620, 0.300),   # 가로등
        "fog": (0.550, 0.650, 0.800),
        "moon": (0.550, 0.650, 1.000),
    },
    "fog": {"density": 0.030, "emission_strength": 0.0015, "emission": (0.35, 0.45, 0.65), "end": 80.0,
            "samples": 128, "tile_size": "2"},
    "lamp": {"energy": 4000.0, "fill_energy": 250.0, "spot_size_deg": 104.0, "blend": 0.62, "head_emission": 40.0,
             # 조명은 기둥 위(4.20)와 전구 아래쪽 끝(4.50-0.18=4.32) 사이에 놓아야 한다.
             # 기둥이나 전구 안에 들어가면 자기 형상에 가려 빛이 한 줄기도 빠져나오지 못한다.
             "post_height": 4.20, "head_z": 4.50, "head_radius": 0.18,
             "spot_z": 4.40, "spot_radius": 0.05, "fill_z": 4.40, "fill_radius": 0.08,
             "flicker_dips": [(0.31, 0.004, 0.55), (0.33, 0.003, 0.35), (0.72, 0.005, 0.45)]},
    "moon": {"energy": 0.035, "volume_factor": 0.0, "rotation_deg": (50.0, 0.0, -30.0)},
    "glare": {"glare_threshold": 0.6, "glare_strength": 0.45, "glare_size": 0.7},
    "rain": {"count": 4000, "lifetime": 40, "emitter_z": 9.0, "emitter_size": 40.0, "seed": 7},
    "cameras": {
        "wide":    {"location": (-0.2, -8.2, 1.50), "target": (1.5, 4.6, 1.55), "lens": 35, "fstop": 2.8,
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
    common.add_plane("ground", 200.0, (0, 0, 0), common.make_material("ground", pal["night"], roughness=0.25))
    common.add_box("road", (120.0, 7.0, 0.10), (0, 0, 0.05), common.make_material("asphalt", pal["asphalt"], roughness=0.07), bevel=0.0)
    common.add_box("sidewalk", (30.0, 3.5, 0.25), (0, 5.25, 0.125), common.make_material("concrete", pal["concrete"], roughness=0.28), bevel=0.02)
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
    common.add_cylinder("lamp_post", 0.06, p["lamp"]["post_height"], (3.5, 4.2, p["lamp"]["post_height"] / 2), steel)
    head = common.make_material("lamp_head", pal["amber"], emission=pal["amber"], emission_strength=p["lamp"]["head_emission"])
    bulb = common.add_sphere("lamp_head", p["lamp"]["head_radius"], (3.5, 4.2, p["lamp"]["head_z"]), head)
    bulb.visible_shadow = False  # 전구가 자기 빛을 가리지 않게 한다
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
    # 설계의 "가늘고 긴 나무 실루엣". 구를 쌓으면 구슬을 꿴 모양이 되므로,
    # 구 하나를 세로로 늘인 타원체로 사이프러스 같은 실루엣을 만든다.
    for i, (x, y, h, w) in enumerate(((-9, 9, 8.0, 0.62), (-4, 12, 10.0, 0.70),
                                      (6, 11, 9.0, 0.55), (12, 9, 7.5, 0.66))):
        common.add_cylinder(f"trunk_{i}", 0.09, h, (x, y, h / 2), dark)
        canopy = common.add_sphere(f"canopy_{i}", 1.0, (x, y, h * 0.62), dark)
        canopy.scale = (w, w, h * 0.33)
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


def build_lighting(p, frame_start, frame_end):
    pal, lamp = p["palette"], p["lamp"]
    spot = common.add_light("lamp_spot", "SPOT", (3.5, 4.2, lamp["spot_z"]), lamp["energy"], pal["amber"],
                            radius=lamp["spot_radius"], spot_size=math.radians(lamp["spot_size_deg"]),
                            spot_blend=lamp["blend"])
    common.add_light("lamp_fill", "POINT", (3.5, 4.2, lamp["fill_z"]), lamp["fill_energy"], pal["amber"],
                     radius=lamp["fill_radius"], volume_factor=0.0)
    rot = tuple(math.radians(v) for v in p["moon"]["rotation_deg"])
    common.add_light("moon", "SUN", (0, 0, 20), p["moon"]["energy"], pal["moon"], rotation=rot, radius=0.05, volume_factor=p["moon"]["volume_factor"])
    # 가로등 깜박임: 주기 함수라 클립을 이어 붙여도 끊기지 않는다
    for frame in range(frame_start, frame_end + 1):
        t = motion.loop_phase(frame, frame_start, frame_end)
        spot.data.energy = lamp["energy"] * motion.flicker_factor(t, lamp["flicker_dips"])
        spot.data.keyframe_insert("energy", frame=frame)
    fog = p["fog"]
    common.setup_world_fog(pal["sky"], pal["fog"], fog["density"], fog["emission"], fog["emission_strength"],
                           end=fog["end"], samples=fog["samples"], tile_size=fog["tile_size"])


def build_rain(p, frame_start, frame_end):
    r = p["rain"]
    emitter = common.add_plane("rain_emitter", r["emitter_size"], (0, 0, r["emitter_z"]), None)
    drop = common.add_cylinder("rain_drop", 0.004, 0.35, (0, 0, -50),
                               common.make_material("rain", (0.8, 0.85, 0.95), roughness=0.1, alpha=0.35), vertices=6)
    mod = emitter.modifiers.new("rain", "PARTICLE_SYSTEM")
    ps = mod.particle_system
    st = ps.settings
    st.count = r["count"]
    st.frame_start = frame_start - r["lifetime"]  # 첫 프레임부터 비가 이미 내리고 있게
    st.frame_end = frame_end
    st.lifetime = r["lifetime"]
    st.render_type = "OBJECT"
    st.instance_object = drop
    st.particle_size = 1.0
    st.normal_factor = 0.0
    st.effector_weights.gravity = 1.0
    ps.seed = r["seed"]
    emitter.show_instancer_for_render = False
    emitter.show_instancer_for_viewport = False


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
    build_lighting(params, frame_start, frame_end)
    build_rain(params, frame_start, frame_end)
    return build_cameras(params, frame_start, frame_end)


if __name__ == "__main__":
    common.run_scene(build, PARAMS)
