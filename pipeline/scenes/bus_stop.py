"""꿈에서 본 듯한 정류장. 기본 도형만으로 짓는다.

호출은 파일 상단 CLI 계약(docs/superpowers/plans/2026-09-02-nameless-city-first-episode.md) 참조.
좌표계: 도로는 X축을 따라 놓이고(y=0 중심, 폭 7m), 인도와 정류장은 +y 쪽이다. 단위는 m.
"""

import math
import random
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
            # 실측(1080p, TAA 64): tile "2"→"4" 는 프레임당 3.05초→2.15초로 싸지지만 빛기둥에
            # 격자 무늬가 돌아온다. samples 128→64 는 화면 차이가 거의 없이 4.23초→3.05초로 준다.
            "samples": 64, "tile_size": "2"},
    "lamp": {"energy": 4000.0, "fill_energy": 250.0, "spot_size_deg": 104.0, "blend": 0.62, "head_emission": 40.0,
             # 조명은 기둥(z 0~4.20) 안에 들어가면 안 된다 — 자기 형상에 가려 빛이 못 빠져나온다.
             # spot_z/fill_z(4.40)는 전구 구체(z 4.32~4.68) 안쪽이지만, build_lamp_and_props 에서
             # 전구에 bulb.visible_shadow = False 를 설정해 자기 그림자를 끄기 때문에 문제 없다.
             "post_height": 4.20, "head_z": 4.50, "head_radius": 0.18,
             "spot_z": 4.40, "spot_radius": 0.05, "fill_z": 4.40, "fill_radius": 0.08,
             "flicker_dips": [(0.31, 0.004, 0.55), (0.33, 0.003, 0.35), (0.72, 0.005, 0.45)]},
    "moon": {"energy": 0.035, "volume_factor": 0.0, "rotation_deg": (50.0, 0.0, -30.0)},
    "glare": {"glare_threshold": 0.6, "glare_strength": 0.45, "glare_size": 0.7},
    # 그림자 해상도/스텝을 낮춘다. 관문 2 실측(TAA 32): 1.56초→1.28초, 스틸 비교로 승인받은
    # 화면과 구분되지 않았다.
    "shadow": {"shadow_resolution_scale": 0.5, "shadow_step_count": 3},
    "rain": {"count": 4000, "lifetime": 40, "emitter_z": 9.0, "emitter_size": 40.0, "seed": 7},
    "cameras": {
        "wide":    {"location": (-0.2, -8.2, 1.50), "target": (1.5, 4.6, 1.55), "lens": 35, "fstop": 2.8,
                    "amplitudes": (0.6, 0.0, 0.08), "harmonics": (1, 1, 2)},
        "shelter": {"location": (-1.2, 5.3, 1.5), "target": (30.0, 2.0, 1.2), "lens": 35, "fstop": 2.0,
                    "amplitudes": (0.4, 0.0, 0.03), "harmonics": (1, 1, 2)},
        "marble":  {"location": (0.9, 4.2, 1.15),
                    # target 은 marble_glass 중심(0.3, 5.0, 0.61)을 그대로 겨냥해야 한다. 위로
                    # 0.34m 만 벗어나도 시선축(카메라→목표점)과 카메라→구슬 방향의 각도가
                    # 17.1도로 벌어지는데, 60mm 렌즈의 세로 반화각은 9.6도뿐이라 구슬이
                    # 프레임 밖으로 나간다.
                    "target": (0.3, 5.0, 0.61), "lens": 60, "fstop": 1.4,
                    "amplitudes": (0.12, 0.08, 0.02), "harmonics": (1, 1, 1)},
        "puddle":  {"location": (1.5, -2.0, 0.25), "target": (2.5, 4.3, 1.0), "lens": 28, "fstop": 2.8,
                    "amplitudes": (0.0, 0.0, 0.15), "harmonics": (1, 1, 1)},
    },
    "bus": {"x_start": -70.0, "x_end": 70.0, "y": 1.8, "headlight_energy": 3000.0},

    # --- 소품(관문 1 반복 중 추가: 형태 디테일 요청) ------------------------------------
    "bevel": {
        # 큰 오브제일수록 베벨 폭을 형태에 맞게 키운다. 가장 얇은 축의 절반을 넘지 않게 확인했다.
        "road": 0.045,       # 얇은 축 z=0.10 → 절반 0.05
        "sidewalk": 0.05,    # 얇은 축 z=0.25 → 절반 0.125
        "roof": 0.02,        # 얇은 축 z=0.06 → 절반 0.03
        "back_wall": 0.008,  # 얇은 축 y=0.03 → 절반 0.015
        "side_glass": 0.01,  # 얇은 축 x=0.03 → 절반 0.015
        "curb": 0.03,        # 얇은 축 z=0.15 → 절반 0.075
    },
    "ground": {
        # 도로·인도 상면 높이는 여러 소품(연석·이음선·배수구·볼라드·낙엽·쓰레기통)이 함께
        # 참조하므로 여기 한 곳에서만 정의하고, 아래 _road_top()/_sidewalk_top() 으로 계산한다.
        "road_size": (120.0, 7.0, 0.10), "road_center": (0.0, 0.0, 0.05),
        "sidewalk_size": (30.0, 3.5, 0.25), "sidewalk_center": (0.0, 5.25, 0.125),
    },
    "bin": {"radius": 0.22, "height": 0.75},
    "curb": {"size": (30.0, 0.20, 0.15), "y": 3.5, "z": 0.175},
    "sidewalk_joints": {
        # 와이드 카메라 시야 안쪽만. 도형 수가 늘지 않게 격자 간격을 넉넉히 둔다.
        "x_range": (-5.0, 5.0), "x_step": 1.25, "y_values": (3.7, 4.7, 5.7, 6.7),
        "width": 0.02, "depth": 0.003,
    },
    "drain": {"x": 4.0, "y": 3.3, "bar_count": 6, "bar_length": 0.5, "bar_width": 0.03, "bar_gap": 0.05,
              "bar_thickness": 0.012},
    "bollards": {"positions": ((-5.0, 3.75), (-6.4, 3.75), (5.6, 3.75)), "radius": 0.075, "height": 0.55,
                 "cap_radius": 0.09, "cap_height": 0.05},
    "side_glass": {"x": 1.46, "y_span": (4.34, 5.86)},
    # 유리는 알파가 높으면 조명을 받아 불투명한 벽처럼 보인다. 배경이 비쳐 보일 만큼 낮춘다.
    "glass": {"color": (0.34, 0.42, 0.52), "alpha": 0.09, "roughness": 0.05},
    "timetable": {"location_xy": (-1.0, 5.87), "z": 1.75, "bezel_size": (0.55, 0.02, 0.42),
                  "panel_size": (0.46, 0.014, 0.34)},
    "bench": {
        "slat_size": (2.0, 0.12, 0.06), "slat_pitch": 0.14, "z": 0.50,
        "backrest_size": (2.0, 0.05, 0.34), "backrest_y": 5.225, "backrest_z": 0.70,
    },
    "rail": {"y": 5.65, "z": 1.0, "radius": 0.022, "half_length": 1.3},
    "roof_gutter": {"thickness": 0.03, "drop": 0.05},
    "bin_detail": {"lid_radius": 0.24, "lid_height": 0.05, "groove_count": 8, "groove_radius": 0.012,
                   "groove_ring_radius": 0.205, "groove_height": 0.55},
    "lamp_base": {"radius": 0.14, "height": 0.15},
    "sign_detail": {"base_radius": 0.09, "base_height": 0.08,
                     "bracket_size": (0.42, 0.03, 0.05), "bracket_z": 1.86},
    "wires": {
        # 전신주 크로스바(x=±14, y=6.5, z=6.6, 크로스바 절반폭 0.8) 사이에 두 줄을 늘어뜨린다.
        "span_x": (-13.2, 13.2), "y_offsets": (0.0, 0.18), "z": 6.6, "sags": (1.3, 1.0), "radius": 0.012,
    },
    "leaves": {"seed": 11, "count": 26, "size_range": (0.09, 0.15),
               "x_range": (-5.0, 6.0), "y_range": (3.6, 6.8), "tilt_range_deg": 9.0},
    "trees": {
        "seed": 5, "branch_count_range": (3, 4), "branch_radius": 0.028,
        "branch_tilt_deg_range": (40.0, 70.0), "branch_start_frac_range": (0.44, 0.62),
        # 캐노피 반지름(w)에 대한 비율. 가지의 수평 도달 거리를 이 값으로 직접 고정하므로
        # (길이는 tilt와 무관하게 reach/sin(tilt)로 역산한다) 1.0 미만으로 두면 가지 끝이
        # 항상 캐노피 안쪽에 머문다.
        "branch_reach_factor_range": (0.55, 0.9),
        "lobe_count_range": (2, 3), "lobe_w_factor_range": (0.75, 1.05), "lobe_h_factor_range": (0.28, 0.38),
        "lobe_xy_jitter_factor": 0.4, "lobe_z_center_frac_range": (0.58, 0.68), "lobe_z_jitter_frac": 0.10,
        # (x, y, 높이, 폭). 설계는 나무가 "안개 속으로 사라진다"고 하므로 충분히 뒤로 물린다.
        "placements": ((-13.0, 16.0, 9.0, 0.44), (-5.0, 18.0, 10.5, 0.50),
                       (7.0, 14.0, 9.5, 0.42), (15.0, 15.0, 8.5, 0.46)),
    },
    "material_variation": {
        # 노이즈 크기(scale)와 거칠기가 오갈 범위(roughness_range), 범프 세기(bump_strength).
        # 좌표는 GENERATED 고정 — common.add_procedural_roughness 참조.
        "asphalt": {"scale": 6.0, "roughness_range": (0.05, 0.34), "bump_strength": 0.015},
        "concrete": {"scale": 9.0, "roughness_range": (0.18, 0.42), "bump_strength": 0.035},
        "steel": {"scale": 22.0, "roughness_range": (0.32, 0.48), "bump_strength": 0.0},
        "glass": {"scale": 5.0, "roughness_range": (0.02, 0.09), "bump_strength": 0.0},
    },
}


def _frange(lo, hi, step):
    count = int(round((hi - lo) / step)) + 1
    return [lo + i * step for i in range(count)]


def _align_to(direction):
    """(0,0,1) 축을 direction 벡터로 향하게 하는 (rx, ry, rz) 오일러. 헤드리스로 실측 확인."""
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    dx, dy, dz = dx / length, dy / length, dz / length
    theta = math.acos(max(-1.0, min(1.0, dz)))
    psi = math.atan2(dy, dx)
    return (0.0, theta, psi)


def _road_top(p):
    g = p["ground"]
    return g["road_center"][2] + g["road_size"][2] / 2


def _sidewalk_top(p):
    g = p["ground"]
    return g["sidewalk_center"][2] + g["sidewalk_size"][2] / 2


def _bin_top(p):
    return _sidewalk_top(p) + p["bin"]["height"]


def build_ground_and_road(p):
    pal = p["palette"]
    bevel = p["bevel"]
    g = p["ground"]
    common.add_plane("ground", 200.0, (0, 0, 0), common.make_material("ground", pal["night"], roughness=0.25))
    asphalt = common.make_material("asphalt", pal["asphalt"], roughness=0.07)
    common.add_box("road", g["road_size"], g["road_center"], asphalt, bevel=bevel["road"])
    concrete = common.make_material("concrete", pal["concrete"], roughness=0.28)
    common.add_box("sidewalk", g["sidewalk_size"], g["sidewalk_center"], concrete, bevel=bevel["sidewalk"])
    common.add_procedural_roughness(asphalt, **p["material_variation"]["asphalt"])
    common.add_procedural_roughness(concrete, **p["material_variation"]["concrete"])
    # 도로 가운데 점선
    dash = common.make_material("dash", (0.35, 0.33, 0.25), roughness=0.5)
    for i in range(-14, 15):
        common.add_box(f"dash_{i}", (2.0, 0.12, 0.01), (i * 4.0, 0, 0.105), dash, bevel=0.0)
    _build_curb(p, concrete)
    _build_sidewalk_joints(p, concrete)
    _build_drain(p)
    _build_bollards(p)


def _build_curb(p, concrete):
    c = p["curb"]
    common.add_box("curb", c["size"], (0, c["y"], c["z"]), concrete, bevel=p["bevel"]["curb"])


def _build_sidewalk_joints(p, concrete):
    j = p["sidewalk_joints"]
    z = _sidewalk_top(p) + 0.001
    xmin, xmax = j["x_range"]
    xs = _frange(xmin, xmax, j["x_step"])
    y_lo, y_hi = 3.5, 7.0
    for i, x in enumerate(xs):
        common.add_box(f"joint_x_{i}", (j["width"], y_hi - y_lo, j["depth"]), (x, (y_lo + y_hi) / 2, z),
                       concrete, bevel=0.0)
    for i, y in enumerate(j["y_values"]):
        common.add_box(f"joint_y_{i}", (xmax - xmin, j["width"], j["depth"]), ((xmin + xmax) / 2, y, z),
                       concrete, bevel=0.0)


def _build_drain(p):
    d = p["drain"]
    road_top = _road_top(p)
    frame = common.make_material("drain_frame", (0.03, 0.035, 0.045), roughness=0.5)
    common.add_box("drain_frame", (d["bar_length"] + 0.06, d["bar_gap"] * d["bar_count"] + 0.04, 0.01),
                   (d["x"], d["y"], road_top + 0.001), frame, bevel=0.0)
    bars = _frange(-(d["bar_count"] - 1) / 2 * d["bar_gap"], (d["bar_count"] - 1) / 2 * d["bar_gap"], d["bar_gap"])
    steel = bpy.data.materials["steel"]
    for i, offset in enumerate(bars):
        common.add_box(f"drain_bar_{i}", (d["bar_length"], d["bar_width"], d["bar_thickness"]),
                       (d["x"], d["y"] + offset, road_top + 0.008), steel, bevel=0.0)


def _build_bollards(p):
    b = p["bollards"]
    steel = bpy.data.materials["steel"]
    top_of_sidewalk = _sidewalk_top(p)
    body_z = top_of_sidewalk + b["height"] / 2
    cap_z = top_of_sidewalk + b["height"]
    for i, (x, y) in enumerate(b["positions"]):
        common.add_cylinder(f"bollard_{i}", b["radius"], b["height"], (x, y, body_z), steel, bevel=0.01)
        common.add_cylinder(f"bollard_{i}_cap", b["cap_radius"], b["cap_height"], (x, y, cap_z), steel, bevel=0.01)


def build_shelter(p):
    pal = p["palette"]
    bevel = p["bevel"]
    # steel 은 build_ground_and_road 의 배수구·볼라드가 먼저 참조하므로 build()에서
    # _build_shared_materials 로 미리 만들어 둔다. 여기서는 이미 만들어진 것을 가져다 쓴다.
    steel = bpy.data.materials["steel"]
    gl = p["glass"]
    glass = common.make_material("glass", gl["color"], roughness=gl["roughness"], alpha=gl["alpha"])
    common.add_procedural_roughness(glass, **p["material_variation"]["glass"])
    for name, (x, y) in {"post_fl": (-1.5, 4.3), "post_fr": (1.5, 4.3), "post_bl": (-1.5, 5.9), "post_br": (1.5, 5.9)}.items():
        common.add_box(name, (0.08, 0.08, 2.6), (x, y, 1.3), steel, bevel=0.01)
    common.add_box("shelter_roof", (3.4, 1.8, 0.06), (0, 5.1, 2.63), glass, bevel=bevel["roof"])
    common.add_box("shelter_back", (3.0, 0.03, 2.2), (0, 5.9, 1.35), glass, bevel=bevel["back_wall"])
    wood = common.make_material("wood", pal["wood"], roughness=0.6)
    for name, x in (("bench_leg_l", -0.8), ("bench_leg_r", 0.8)):
        common.add_box(name, (0.06, 0.38, 0.45), (x, 5.0, 0.24), steel, bevel=0.005)
    _build_bench(p, wood)
    _build_side_glass(p, glass)
    _build_timetable(p)
    _build_rail(p, steel)
    _build_roof_gutter(p, steel)


def _build_bench(p, wood):
    b = p["bench"]
    sx, sy, sz = b["slat_size"]
    pitch = b["slat_pitch"]
    offsets_names = ((-pitch, "bench_slat_front"), (0.0, "bench_seat"), (pitch, "bench_slat_back"))
    for offset, name in offsets_names:
        common.add_box(name, (sx, sy, sz), (0, 5.0 + offset, b["z"]), wood, bevel=0.01)
    common.add_box("bench_backrest", b["backrest_size"], (0, b["backrest_y"], b["backrest_z"]), wood, bevel=0.01)


def _build_side_glass(p, glass):
    g = p["side_glass"]
    y_lo, y_hi = g["y_span"]
    size = (0.03, y_hi - y_lo, 2.2)
    common.add_box("shelter_side_l", size, (-g["x"], (y_lo + y_hi) / 2, 1.35), glass, bevel=p["bevel"]["side_glass"])
    common.add_box("shelter_side_r", size, (g["x"], (y_lo + y_hi) / 2, 1.35), glass, bevel=p["bevel"]["side_glass"])


def _build_timetable(p):
    t = p["timetable"]
    x, y = t["location_xy"]
    bezel = common.make_material("timetable_bezel", (0.05, 0.06, 0.08), roughness=0.45, metallic=0.1)
    panel = common.make_material("timetable_panel", (0.55, 0.52, 0.42), roughness=0.35)
    common.add_box("timetable_bezel", t["bezel_size"], (x, y, t["z"]), bezel, bevel=0.005)
    inner_y = y - 0.015  # 베젤보다 살짝 앞(부스 안쪽)으로 나와야 액자처럼 보인다
    common.add_box("timetable_panel", t["panel_size"], (x, inner_y, t["z"]), panel, bevel=0.0)


def _build_rail(p, steel):
    r = p["rail"]
    common.add_cylinder("lean_rail", r["radius"], r["half_length"] * 2, (0, r["y"], r["z"]), steel,
                        rotation=(0, math.radians(90), 0))


def _build_roof_gutter(p, steel):
    g = p["roof_gutter"]
    roof_bottom = 2.63 - 0.03
    z = roof_bottom - g["drop"] / 2
    common.add_box("roof_gutter_front", (3.4, g["thickness"], g["drop"]), (0, 5.1 - 0.9, z), steel, bevel=0.0)
    common.add_box("roof_gutter_back", (3.4, g["thickness"], g["drop"]), (0, 5.1 + 0.9, z), steel, bevel=0.0)
    common.add_box("roof_gutter_left", (g["thickness"], 1.8, g["drop"]), (-1.7, 5.1, z), steel, bevel=0.0)
    common.add_box("roof_gutter_right", (g["thickness"], 1.8, g["drop"]), (1.7, 5.1, z), steel, bevel=0.0)


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
    bin_cfg = p["bin"]
    common.add_cylinder("bin", bin_cfg["radius"], bin_cfg["height"],
                        (2.2, 4.3, _sidewalk_top(p) + bin_cfg["height"] / 2),
                        common.make_material("bin", (0.05, 0.06, 0.07), roughness=0.5), bevel=0.02)
    # 유리구슬: 벤치 위. 안에 아주 작은 행성
    marble = common.make_material("marble", (0.9, 0.95, 1.0), roughness=0.0, transmission=1.0, ior=1.5)
    common.add_sphere("marble_glass", 0.08, (0.3, 5.0, 0.53 + 0.08), marble)
    common.add_sphere("marble_core", 0.025, (0.3, 5.0, 0.61),
                      common.make_material("marble_core", (0.2, 0.3, 0.6), emission=(0.4, 0.6, 1.0), emission_strength=3.0))
    _build_lamp_base(p, steel)
    _build_sign_detail(p, steel)
    _build_bin_detail(p)


def _build_lamp_base(p, steel):
    lb = p["lamp_base"]
    common.add_cylinder("lamp_post_base", lb["radius"], lb["height"], (3.5, 4.2, lb["height"] / 2), steel, bevel=0.01)


def _build_sign_detail(p, steel):
    s = p["sign_detail"]
    common.add_cylinder("sign_pole_base", s["base_radius"], s["base_height"], (-2.5, 4.1, s["base_height"] / 2),
                        steel, bevel=0.01)
    bracket = common.make_material("sign_bracket", (0.06, 0.07, 0.09), roughness=0.4, metallic=0.2)
    common.add_box("sign_bracket", s["bracket_size"], (-2.5, 4.1 + 0.035, s["bracket_z"]), bracket, bevel=0.005)


def _build_bin_detail(p):
    d = p["bin_detail"]
    bin_mat = bpy.data.materials["bin"]
    top = _bin_top(p)
    bin_mid_z = _sidewalk_top(p) + p["bin"]["height"] / 2
    common.add_cylinder("bin_lid", d["lid_radius"], d["lid_height"], (2.2, 4.3, top - d["lid_height"] / 2),
                        bin_mat, bevel=0.01)
    for i in range(d["groove_count"]):
        angle = i * (2.0 * math.pi / d["groove_count"])
        x = 2.2 + d["groove_ring_radius"] * math.cos(angle)
        y = 4.3 + d["groove_ring_radius"] * math.sin(angle)
        common.add_cylinder(f"bin_groove_{i}", d["groove_radius"], d["groove_height"], (x, y, bin_mid_z),
                            bin_mat)


def build_background(p):
    pal = p["palette"]
    dark = common.make_material("silhouette", (0.012, 0.014, 0.020), roughness=0.9)
    # 설계의 "가늘고 긴 나무 실루엣". 구를 쌓으면 구슬을 꿴 모양이 되므로,
    # 구 하나를 세로로 늘인 타원체로 사이프러스 같은 실루엣을 만든다. 가지와 캐노피 여러 겹은
    # 나무마다 독립된 random.Random(f"{시드}-{나무 인덱스}") 인스턴스로 흔든다. 나무 하나를
    # 더하거나 빼거나 그 나무의 형태 파라미터만 바꿔도 다른 나무의 난수 소비 위치가 밀리지
    # 않도록 하기 위해서다(하나의 rng를 공유하면 이 국지성이 깨진다). 시드는 고정이라 매
    # 실행 동일하게 만든다.
    seed = p["trees"]["seed"]
    for i, (x, y, h, w) in enumerate(p["trees"]["placements"]):
        rng = random.Random(f"{seed}-{i}")
        _build_tree(p, f"tree{i}", x, y, h, w, dark, rng)
    for i, x in enumerate((-14.0, 14.0)):
        common.add_cylinder(f"pole_{i}", 0.10, 7.0, (x, 6.5, 3.5), dark)
        common.add_box(f"crossbar_{i}", (1.6, 0.08, 0.08), (x, 6.5, 6.6), dark, bevel=0.0)
    _build_power_lines(p, dark)
    # 멀리 보이는 다른 정류장의 불빛
    far = common.make_material("far_light", pal["amber"], emission=pal["amber"], emission_strength=20.0)
    common.add_sphere("far_light", 0.12, (55.0, 6.0, 3.0), far)


def _build_tree(p, prefix, x, y, h, w, dark, rng):
    t = p["trees"]
    common.add_cylinder(f"{prefix}_trunk", 0.09, h, (x, y, h / 2), dark)
    branch_count = rng.randint(*t["branch_count_range"])
    for bi in range(branch_count):
        angle = rng.uniform(0, 2.0 * math.pi)
        tilt = math.radians(rng.uniform(*t["branch_tilt_deg_range"]))
        start_h = h * rng.uniform(*t["branch_start_frac_range"])
        reach = w * rng.uniform(*t["branch_reach_factor_range"])  # 캐노피 안쪽에 머무는 수평 도달 거리
        length = reach / math.sin(tilt)
        direction = (math.sin(tilt) * math.cos(angle), math.sin(tilt) * math.sin(angle), math.cos(tilt))
        start = (x, y, start_h)
        end = tuple(start[i] + direction[i] * length for i in range(3))
        mid = tuple((start[i] + end[i]) / 2 for i in range(3))
        common.add_cylinder(f"{prefix}_branch_{bi}", t["branch_radius"], length, mid, dark,
                            rotation=_align_to(direction))
    lobe_count = rng.randint(*t["lobe_count_range"])
    for li in range(lobe_count):
        lobe_w = w * rng.uniform(*t["lobe_w_factor_range"])
        lobe_h = h * rng.uniform(*t["lobe_h_factor_range"])
        jitter = w * t["lobe_xy_jitter_factor"]
        offset_x = rng.uniform(-jitter, jitter)
        offset_y = rng.uniform(-jitter, jitter)
        z_jitter = h * t["lobe_z_jitter_frac"]
        center_z = h * rng.uniform(*t["lobe_z_center_frac_range"]) + rng.uniform(-z_jitter, z_jitter)
        canopy = common.add_sphere(f"{prefix}_canopy_{li}", 1.0, (x + offset_x, y + offset_y, center_z), dark)
        canopy.scale = (lobe_w, lobe_w, lobe_h)


def _build_power_lines(p, dark):
    w = p["wires"]
    x0, x1 = w["span_x"]
    for i, y_offset in enumerate(w["y_offsets"]):
        y = 6.5 + y_offset
        common.add_sag_curve(f"power_wire_{i}", (x0, y, w["z"]), (x1, y, w["z"]), w["sags"][i], dark,
                             radius=w["radius"])


def build_puddles(p):
    water = common.make_material("water", (0.010, 0.012, 0.018), roughness=0.03)
    for i, (x, y, r) in enumerate(((1.0, -1.5, 1.6), (-3.0, 2.2, 1.1), (2.6, 3.9, 0.7))):
        common.add_cylinder(f"puddle_{i}", r, 0.006, (x, y, 0.103 if y < 3.5 else 0.253), water, vertices=48)


def build_leaves(p):
    """젖은 바닥의 낙엽 몇 장. 아주 얇은 평면을 무작위 회전으로 흩뿌리되 고정 시드를 쓴다."""
    leaf = common.make_material("leaf", (0.26, 0.16, 0.05), roughness=0.55)
    cfg = p["leaves"]
    rng = random.Random(cfg["seed"])
    tilt = math.radians(cfg["tilt_range_deg"])
    for i in range(cfg["count"]):
        x = rng.uniform(*cfg["x_range"])
        y = rng.uniform(*cfg["y_range"])
        on_sidewalk = y >= 3.5
        z = (_sidewalk_top(p) + 0.006) if on_sidewalk else (_road_top(p) + 0.006)
        size = rng.uniform(*cfg["size_range"])
        rotation = (rng.uniform(-tilt, tilt), rng.uniform(-tilt, tilt), rng.uniform(0, 2.0 * math.pi))
        common.add_plane(f"leaf_{i}", size, (x, y, z), leaf, rotation=rotation)


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


def build_bus(p, frame_start, frame_end):
    b = p["bus"]
    road_top = _road_top(p)
    root = bpy.data.objects.new("bus", None)
    bpy.context.scene.collection.objects.link(root)
    body_mat = common.make_material("bus_body", (0.05, 0.06, 0.08), roughness=0.35)
    body = common.add_box("bus_body", (10.0, 2.6, 3.0), (0, 0, road_top + 1.5), body_mat, bevel=0.08)
    win = common.make_material("bus_window", (0.6, 0.55, 0.4), emission=(1.0, 0.85, 0.6), emission_strength=2.0)
    windows = common.add_box("bus_windows", (8.5, 2.64, 1.0), (0.2, 0, road_top + 2.2), win, bevel=0.0)
    tail = common.make_material("bus_tail", (0.8, 0.05, 0.02), emission=(1.0, 0.08, 0.03), emission_strength=25.0)
    tail_l = common.add_box("bus_tail_l", (0.05, 0.25, 0.18), (-5.03, 0.9, road_top + 0.9), tail, bevel=0.0)
    tail_r = common.add_box("bus_tail_r", (0.05, 0.25, 0.18), (-5.03, -0.9, road_top + 0.9), tail, bevel=0.0)
    parts = [body, windows, tail_l, tail_r]
    # 전조등: 진행 방향(+x)을 향하는 스폿. 스폿은 로컬 -Z를 비추므로 Y축 -90도 회전
    for name, y in (("bus_head_l", 0.9), ("bus_head_r", -0.9)):
        parts.append(common.add_light(name, "SPOT", (5.05, y, road_top + 0.9), b["headlight_energy"], (1.0, 0.9, 0.7),
                                      rotation=(0, math.radians(-90), 0), radius=0.15,
                                      spot_size=math.radians(50), spot_blend=0.4, volume_factor=1.5))
    for part in parts:
        part.parent = root
    # 등속 통과: smoothstep을 쓰지 않는다(버스는 멈추지 않는다)
    for frame in range(frame_start, frame_end + 1):
        t = (frame - frame_start) / max(frame_end - frame_start, 1)
        root.location = (b["x_start"] + (b["x_end"] - b["x_start"]) * t, b["y"], 0.0)
        root.keyframe_insert("location", frame=frame)


def build_cameras(p, frame_start, frame_end):
    cams = {}
    marble = bpy.data.objects["marble_glass"]
    for name, c in p["cameras"].items():
        cam = common.add_camera(name, c["location"], c["target"], lens=c["lens"], fstop=c["fstop"],
                                focus_target=marble if name == "marble" else None)
        common.keyframe_loop_motion(cam, c["location"], c["amplitudes"], frame_start, frame_end, c["harmonics"])
        cams[name] = cam
    return cams


def _build_shared_materials(p):
    """여러 build_* 함수가 공유하는 머티리얼. 처음 쓰이는 함수보다 먼저 만들어야 한다.

    steel 은 원래 build_shelter 에서 만들었지만, 배수구·볼라드(build_ground_and_road)가
    그보다 먼저 실행되며 steel 을 참조하므로 build() 맨 앞으로 끌어올렸다.
    """
    steel = common.make_material("steel", p["palette"]["steel"], roughness=0.4, metallic=0.3)
    common.add_procedural_roughness(steel, **p["material_variation"]["steel"])


def build(params, frame_start, frame_end, event):
    _build_shared_materials(params)
    build_ground_and_road(params)
    build_shelter(params)
    build_lamp_and_props(params)
    build_background(params)
    build_puddles(params)
    build_leaves(params)
    build_lighting(params, frame_start, frame_end)
    build_rain(params, frame_start, frame_end)
    if event == "bus":
        build_bus(params, frame_start, frame_end)
    return build_cameras(params, frame_start, frame_end)


if __name__ == "__main__":
    common.run_scene(build, PARAMS)
