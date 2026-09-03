"""행성 프레임 샷: 어두운 우주의 행성으로 내려가거나(descend) 올라온다(ascend).

모든 회차가 공유하는 도입·마무리. 카메라 이름은 main 하나다.
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
    "planet": {"radius": 10.0, "color": (0.020, 0.030, 0.060), "roughness": 0.9},
    "stars": {"count": 600, "shell_radius": 120.0, "size": 0.12, "seed": 3},
    "cities": {"count": 12, "seed": 5, "emission": (1.0, 0.62, 0.3), "strength": 30.0, "size": 0.16},
    "sun": {"energy": 2.0, "color": (0.45, 0.55, 0.9), "rotation_deg": (60.0, 0.0, 40.0)},
    "glare": {"glare_threshold": 0.8, "glare_strength": 0.35, "glare_size": 0.7},
    # near: 40mm 렌즈의 가로 화각(~48.5도)과 행성 반지름(10)으로 2*asin(10/d)가 화각과
    # 비슷해지는 거리가 d≈26. 이보다 가까우면 화면 전체가 표면으로 덮여 형태가 안 보인다
    # (관문 2 반복 중 실측: d=13.73이었을 때 근접 컷이 빈 화면으로 나와 d≈26으로 늘렸다).
    "camera": {"far": (0.0, -48.0, 9.0), "near": (0.0, -25.5, 4.7), "target": (0.0, 0.0, 0.0), "lens": 40, "fstop": 4.0},
}


def build_space(p):
    common.setup_world_fog((0.0, 0.0, 0.002), (0, 0, 0), 0.0, (0, 0, 0), 0.0, samples=16)
    rng = random.Random(p["stars"]["seed"])
    star_mat = common.make_material("star", (1, 1, 1), emission=(0.9, 0.95, 1.0), emission_strength=8.0)
    r = p["stars"]["shell_radius"]
    for i in range(p["stars"]["count"]):
        theta, phi = rng.uniform(0, 2 * math.pi), math.acos(rng.uniform(-1, 1))
        loc = (r * math.sin(phi) * math.cos(theta), r * math.sin(phi) * math.sin(theta), r * math.cos(phi))
        common.add_sphere(f"star_{i}", p["stars"]["size"] * rng.uniform(0.5, 1.5), loc, star_mat)


def build_planet(p):
    pl = p["planet"]
    common.add_sphere("planet", pl["radius"], (0, 0, 0), common.make_material("planet", pl["color"], roughness=pl["roughness"]))
    c = p["cities"]
    rng = random.Random(c["seed"])
    city_mat = common.make_material("city", c["emission"], emission=c["emission"], emission_strength=c["strength"])
    for i in range(c["count"]):
        # 카메라 쪽(-y 반구)에 치우치게 뿌려서 화면에 빛점이 보이게 한다
        theta, phi = rng.uniform(math.pi * 1.15, math.pi * 1.85), rng.uniform(math.pi * 0.25, math.pi * 0.75)
        rr = pl["radius"] + 0.05
        loc = (rr * math.sin(phi) * math.cos(theta), rr * math.sin(phi) * math.sin(theta), rr * math.cos(phi))
        common.add_sphere(f"city_{i}", c["size"], loc, city_mat)
    rot = tuple(math.radians(v) for v in p["sun"]["rotation_deg"])
    common.add_light("sun", "SUN", (0, 0, 30), p["sun"]["energy"], p["sun"]["color"], rotation=rot, radius=0.02, volume_factor=0.0)


def build_camera(p, frame_start, frame_end, event):
    c = p["camera"]
    cam = common.add_camera("main", c["far"], c["target"], lens=c["lens"], fstop=c["fstop"])
    start, end = (c["far"], c["near"]) if event != "ascend" else (c["near"], c["far"])
    for frame in range(frame_start, frame_end + 1):
        t = motion.smoothstep((frame - frame_start) / max(frame_end - frame_start, 1))
        cam.location = tuple(start[i] + (end[i] - start[i]) * t for i in range(3))
        cam.keyframe_insert("location", frame=frame)
    return {"main": cam}


def build(params, frame_start, frame_end, event):
    build_space(params)
    build_planet(params)
    return build_camera(params, frame_start, frame_end, event)


if __name__ == "__main__":
    common.run_scene(build, PARAMS)
