"""common 헬퍼로 최소 장면(바닥·큐브·가로등·안개·카메라)을 짓고 스틸 한 장을 렌더한다.

호출: Blender -b --python-exit-code 1 --python tests/bpy_scripts/common_smoke.py -- --out <png>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline" / "scenes"))

import bpy  # noqa: E402
import common  # noqa: E402

args = common.parse_scene_args()
common.clear_scene()
common.setup_render((160, 90), 24, 1, 4, samples=8)

ground = common.make_material("ground", (0.08, 0.09, 0.11), roughness=0.2)
common.add_plane("ground", 40.0, (0, 0, 0), ground)
common.add_box("cube", (1.0, 1.0, 1.0), (0, 0, 0.5), common.make_material("cube", (0.4, 0.4, 0.5)))
common.add_sphere("bulb", 0.15, (1.5, 0, 4.0),
                  common.make_material("bulb", (1, 0.7, 0.3), emission=(1, 0.6, 0.25), emission_strength=40))
common.add_light("lamp", "SPOT", (1.5, 0, 3.9), 2000, (1, 0.62, 0.3), spot_size=2.0)
common.setup_world_fog((0.01, 0.015, 0.03), (0.55, 0.65, 0.8), 0.02, (0.35, 0.45, 0.65), 0.004, samples=16)
cam = common.add_camera("cam", (7, -7, 2.2), (0.8, 0, 1.4), lens=32, fstop=2.0)
common.keyframe_loop_motion(cam, (7, -7, 2.2), (0.3, 0.0, 0.05), 1, 4)
bpy.context.scene.camera = cam

if args.check:
    common.dump_check({"smoke": True})
else:
    common.render_still(Path(args.out), 2)
