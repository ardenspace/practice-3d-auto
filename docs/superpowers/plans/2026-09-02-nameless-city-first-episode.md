# 무명도시 첫 영상(꿈에서 본 듯한 정류장) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기본 도형으로 지은 정류장 장면을 Blender 파이썬 스크립트 한 벌로 구축하고, Eevee 헤드리스 렌더와 ffmpeg 조립을 거쳐 30분 롱폼 영상 한 편을 완성한다. 설계 문서의 4관문(스틸 → 10초 → 2분 루프+버스 → 30분 완성본)을 순서대로 통과한다.

**Architecture:** 장면 구축·렌더는 Blender 내부 파이썬(bpy)만 쓰는 `pipeline/scenes/` 스크립트가 담당하고, venv 쪽 `pipeline/render_shot.py`가 헤드리스 Blender를 서브프로세스로 띄워 클립(mp4)이나 스틸(png)을 받는다. `pipeline/assemble.py`가 ffmpeg로 클립들을 교차 배열해 롱폼을 만들고, `pipeline/run_episode.py`가 회차 정의(JSON)를 읽어 렌더와 조립을 한 번에 돌린다. 두 세계(bpy ↔ venv)는 파일과 CLI 인자로만 통신한다.

**Tech Stack:** Python 3.12 venv(pytest만 추가로 필요), Blender 5.2 LTS 헤드리스(bpy, Eevee, 컴포지터 글레어, 파티클), ffmpeg 8.1, Blender MCP(look-dev 시 뷰포트 확인용).

**Spec:** `docs/superpowers/specs/2026-09-02-nameless-city-first-episode-design.md`

## Global Constraints

- 유료 API를 호출하지 않는다. 렌더는 로컬 Blender, 조립은 로컬 ffmpeg만 쓴다.
- Blender 실행 파일: `/Applications/Blender.app/Contents/MacOS/Blender` (env `VW_BLENDER_BIN`으로 재정의 가능, `pipeline/config.py`의 `BLENDER_BIN`).
- 기준 규격: 가로 1920×1080, 24fps. 테스트와 프리뷰는 저해상도(160×90 또는 320×180)와 적은 샘플로 돌린다.
- `pipeline/scenes/` 아래 파일은 Blender 내부 파이썬(3.13)에서 실행되므로 **bpy와 표준 라이브러리만 import한다.** numpy, PIL 등 venv 패키지는 절대 쓰지 않는다. venv 쪽 코드(`pipeline/render_shot.py` 등)는 반대로 bpy를 import하지 않는다.
- 이 저장소의 Blender 5.2에서 실측으로 확인된 API 사실. 계획의 코드는 전부 이것을 전제로 한다.
  - 렌더 엔진 식별자는 `"BLENDER_EEVEE"` 하나뿐이다(`BLENDER_EEVEE_NEXT` 없음).
  - 컴포지터는 `scene.compositing_node_group`에 `CompositorNodeTree` 노드 그룹을 대입한다. `CompositorNodeComposite` 노드는 없고, `NodeGroupOutput` 노드와 `ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")`로 출력한다.
  - 글레어 노드의 종류는 `glare.inputs["Type"].default_value = "Bloom"`처럼 소켓으로 정한다(`glare_type` 속성 없음). 소켓 이름: `Threshold`, `Strength`, `Size`.
  - 새 머티리얼은 생성 즉시 `node_tree`와 `Principled BSDF` 노드를 가진다. `use_nodes`를 대입하지 않는다(DeprecationWarning).
  - 안개는 월드 노드 트리에 `ShaderNodeVolumePrincipled`를 `World Output`의 `Volume`에 연결한다. 밀도 0.05 이상이면 배경이 완전히 검게 되므로 **기본 밀도는 0.02~0.03**, 안개 자체에 약한 `Emission Strength`(0.004 안팎)와 희미한 SUN 달빛을 함께 둔다.
  - 1080p, 64샘플, 볼륨 안개·파티클·글레어를 켠 상태에서 프레임당 약 0.75초가 걸린다(M4 Pro 실측).
  - `--python` 스크립트의 예외로 Blender가 0이 아닌 코드로 종료하게 하려면 `--python-exit-code 1`을 함께 준다.
- 커밋 메시지는 한국어로 쓰고, 각 태스크 끝에서 커밋한다. 커밋 본문 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`를 붙인다.
- **관문 1~4는 사용자 승인 게이트다.** 각 관문에서 결과물(png 또는 mp4 경로)을 사용자에게 보여 주고, "예쁘다/다음"이라는 답을 받기 전에는 다음 태스크로 넘어가지 않는다. 사용자의 수정 요청은 `PARAMS` 값이나 `build_*` 함수를 고쳐 반영하고 같은 관문을 다시 돈다.
- 기존 파일(`pipeline/depth.py`, `pipeline/layers.py`, `pipeline/render.py`, `pipeline/blender/parallax_scene.py`, `episodes/pilot-test/`, 관련 테스트)은 삭제하거나 수정하지 않는다.

## 파일 구조

| 파일 | 역할 |
|---|---|
| `pipeline/scenes/__init__.py` | 빈 파일. 패키지 표시용 |
| `pipeline/scenes/motion.py` | 루프 곡선·깜박임·이징 같은 순수 수학 함수. bpy를 import하지 않아 pytest에서 직접 테스트한다 |
| `pipeline/scenes/common.py` | bpy 헬퍼: 장면 비우기, 인자 파싱, 재질·도형·조명·카메라 생성, 월드 안개, 렌더 설정(글레어 포함), 스틸·애니메이션 출력, 체크 덤프 |
| `pipeline/scenes/bus_stop.py` | 정류장 장면. 맨 위 `PARAMS`, `build_*` 함수들, `build()`, `main()` |
| `pipeline/scenes/planet.py` | 행성 도입·마무리 장면. 같은 CLI 계약 |
| `pipeline/render_shot.py` | venv 쪽 러너. `render_clip()`, `check_scene()` |
| `pipeline/assemble.py` | ffmpeg 조립. `build_sequence()`, `assemble()`, `repeat_clip()`, `probe_duration()` |
| `pipeline/run_episode.py` | 회차 JSON을 읽어 클립 렌더 → 조립 |
| `episodes/dream-bus-stop/shots.json` | 첫 회차 정의 |
| `tests/bpy_scripts/common_smoke.py` | Blender 안에서 common 헬퍼를 돌려 보는 테스트 전용 스크립트 |
| `tests/test_motion.py`, `tests/test_scene_common.py`, `tests/test_bus_stop_scene.py`, `tests/test_render_shot.py`, `tests/test_planet_scene.py`, `tests/test_assemble.py`, `tests/test_run_episode.py` | 태스크별 테스트 |

### 장면 스크립트 CLI 계약 (모든 장면 공통)

```text
Blender --background --python-exit-code 1 --python pipeline/scenes/<scene>.py -- \
  --camera <이름> --out <경로> --frame-start N --frame-end N \
  --resolution WxH --fps N --samples N --event <none|bus|descend|ascend> [--still] [--check]
```

- `--check`: 장면을 짓고 `CHECK:{json}` 한 줄을 stdout에 출력한 뒤 렌더 없이 끝난다.
- `--still`: `--frame-start` 프레임 한 장을 `--out`(png)으로 렌더한다.
- 둘 다 없으면 `--frame-start`~`--frame-end`를 렌더한다. **`--out`은 이때 mp4 경로가 아니라 PNG
  연속 이미지 파일명 접두어다**(예: `.../wide.mp4.frames/frame_` → `frame_0001.png`, `frame_0002.png`, ...).
  `scene.render.use_overwrite = False`로 이미 있는 프레임은 건너뛴다(`use_placeholder`는 켜지
  않는다 — 켜면 죽은 프레임이 완료된 것처럼 보인다). mp4로 합치는 것은 장면 스크립트가 아니라
  venv 쪽 `pipeline/render_shot.py`의 책임이다: PNG 작업 디렉터리를 만들고, Blender로 빈
  프레임만 채운 뒤, ffmpeg으로 인코딩하고, 성공하면 PNG를 지운다. 재개(같은 명령을 다시
  실행하면 없는 프레임만 렌더)와, 죽다 만 마지막 프레임 보호(재개 전 가장 번호가 큰 PNG
  하나를 지우고 시작)가 이 경로에서 이루어진다.
- `--event`는 장면이 해석한다. 정류장은 `bus`, 행성은 `descend`/`ascend`를 안다. 모르는 값은 `none`처럼 취급한다.

---

### Task 1: 순수 수학 모듈과 bpy 공통 헬퍼

**Files:**
- Create: `pipeline/scenes/__init__.py`, `pipeline/scenes/motion.py`, `pipeline/scenes/common.py`
- Create: `tests/test_motion.py`, `tests/bpy_scripts/common_smoke.py`, `tests/test_scene_common.py`

**Interfaces:**
- Consumes: `pipeline.config.BLENDER_BIN`, `pipeline.config.PROJECT_ROOT`.
- Produces:
  - `motion.loop_phase(frame, frame_start, frame_end) -> float` (0.0 이상 1.0 미만)
  - `motion.loop_offset(t, amplitude, harmonics=1) -> float`
  - `motion.smoothstep(t) -> float`
  - `motion.flicker_factor(t, dips) -> float` (`dips`: `[(center, width, depth), ...]`)
  - `common.parse_scene_args() -> argparse.Namespace` (camera, out, frame_start, frame_end, resolution "WxH", fps, samples, still, event, check)
  - `common.clear_scene()`
  - `common.make_material(name, color, roughness=0.6, metallic=0.0, emission=None, emission_strength=0.0, alpha=1.0, transmission=0.0, ior=1.45)`
  - `common.add_box(name, size, location, material, bevel=0.03)`, `common.add_cylinder(name, radius, depth, location, material, bevel=0.0, vertices=24, rotation=(0,0,0))`, `common.add_sphere(name, radius, location, material)`, `common.add_plane(name, size, location, material, rotation=(0,0,0))`
  - `common.add_light(name, kind, location, energy, color, rotation=(0,0,0), radius=0.25, spot_size=math.radians(90), spot_blend=0.5, volume_factor=1.0)`
  - `common.add_camera(name, location, target, lens=35, fstop=2.0, focus_target=None)` → 카메라 오브젝트(TRACK_TO로 `target` 지점을 바라봄)
  - `common.keyframe_loop_motion(obj, base, amplitudes, frame_start, frame_end, harmonics=(1,1,1))`
  - `common.setup_world_fog(background, fog_color, density, emission_color, emission_strength, end=80.0, samples=64)`
  - `common.setup_render(resolution, fps, frame_start, frame_end, samples, glare_threshold=1.0, glare_strength=0.25, glare_size=0.6)`
  - `common.render_still(out_path, frame)`, `common.render_animation(out_path)`, `common.dump_check(extra=None)`
  - `common.run_scene(build, params)`: 인자 파싱 → 비우기 → 렌더 설정 → `build(params, frame_start, frame_end, event) -> dict[str, camera_obj]` 호출 → 카메라 선택 → check/still/animation 분기

- [ ] **Step 1: motion.py의 실패하는 테스트 작성** — `tests/test_motion.py`

```python
import math

from pipeline.scenes.motion import flicker_factor, loop_offset, loop_phase, smoothstep


def test_loop_phase_starts_at_zero_and_wraps_before_one():
    assert loop_phase(1, 1, 48) == 0.0
    assert loop_phase(48, 1, 48) < 1.0
    # frame_end+1 은 정확히 한 바퀴(1.0)라서 다음 클립의 첫 프레임과 이어진다
    assert math.isclose(loop_phase(49, 1, 48), 1.0)


def test_loop_offset_is_periodic():
    assert math.isclose(loop_offset(0.0, 0.5), loop_offset(1.0, 0.5), abs_tol=1e-9)
    assert math.isclose(loop_offset(0.25, 0.5), 0.5)
    assert math.isclose(loop_offset(0.25, 0.5, harmonics=2), 0.0, abs_tol=1e-9)


def test_smoothstep_clamps_and_eases():
    assert smoothstep(-1.0) == 0.0
    assert smoothstep(2.0) == 1.0
    assert math.isclose(smoothstep(0.5), 0.5)
    assert smoothstep(0.1) < 0.1  # 시작이 느리다


def test_flicker_factor_dips_only_near_centers():
    dips = [(0.5, 0.01, 0.6)]
    assert math.isclose(flicker_factor(0.5, dips), 0.4, abs_tol=1e-6)
    assert flicker_factor(0.1, dips) > 0.99
    # 주기 경계를 넘어가는 딥도 양쪽에서 같은 값이 나온다(순환)
    wrap = [(0.0, 0.02, 0.5)]
    assert math.isclose(flicker_factor(0.995, wrap), flicker_factor(0.005, wrap), abs_tol=1e-9)
```

- [ ] **Step 2: 실패 확인**

Run: `source .venv/bin/activate && pytest tests/test_motion.py -v`
Expected: FAIL (`ModuleNotFoundError: pipeline.scenes`)

- [ ] **Step 3: motion.py 구현**

`pipeline/scenes/__init__.py`: 빈 파일.

`pipeline/scenes/motion.py`:

```python
"""루프·깜박임·이징용 순수 수학. bpy를 import하지 않으므로 pytest에서 바로 테스트한다."""

import math


def loop_phase(frame: int, frame_start: int, frame_end: int) -> float:
    """frame_start → 0.0, frame_end+1 → 1.0.

    마지막 프레임 다음이 첫 프레임과 정확히 한 주기 떨어지도록 (길이+1)로 나눈다.
    이렇게 해야 클립을 이어 붙였을 때 위치와 속도가 모두 이어진다.
    """
    return (frame - frame_start) / (frame_end - frame_start + 1)


def loop_offset(t: float, amplitude: float, harmonics: int = 1) -> float:
    """주기 1의 사인 곡선. t=0과 t=1에서 값·기울기가 같다."""
    return amplitude * math.sin(2.0 * math.pi * t * harmonics)


def smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def flicker_factor(t: float, dips) -> float:
    """가로등 밝기 배율(0~1). dips는 (center, width, depth) 목록, 모두 주기 1 기준.

    가우시안 딥을 주기 경계 양쪽으로 감싸서 계산하므로 순환 클립에서도 매끄럽다.
    """
    factor = 1.0
    for center, width, depth in dips:
        for wrap in (-1.0, 0.0, 1.0):
            d = (t - (center + wrap)) / width
            factor -= depth * math.exp(-d * d)
    return max(0.0, factor)
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_motion.py -v`
Expected: 4 PASS

- [ ] **Step 5: common.py 실패하는 테스트 작성**

`tests/bpy_scripts/common_smoke.py` (Blender 안에서 실행되는 스크립트):

```python
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
```

`tests/test_scene_common.py`:

```python
import json
import subprocess
from pathlib import Path

from PIL import Image

from pipeline.config import BLENDER_BIN, PROJECT_ROOT

SMOKE = PROJECT_ROOT / "tests" / "bpy_scripts" / "common_smoke.py"


def _run(extra):
    return subprocess.run(
        [BLENDER_BIN, "--background", "--python-exit-code", "1", "--python", str(SMOKE), "--", *extra],
        capture_output=True, text=True, check=True, cwd=PROJECT_ROOT,
    )


def test_common_helpers_render_a_still(tmp_path):
    out = tmp_path / "smoke.png"
    _run(["--out", str(out)])
    assert out.exists()
    img = Image.open(out)
    assert img.size == (160, 90)
    # 완전히 검거나 완전히 흰 이미지는 실패로 본다(조명·안개·컴포지터 중 무언가가 죽은 것)
    mean = sum(img.convert("L").getdata()) / (160 * 90)
    assert 3 < mean < 250


def test_common_check_dumps_json():
    proc = _run(["--check", "--out", "unused"])
    line = next(l for l in proc.stdout.splitlines() if l.startswith("CHECK:"))
    info = json.loads(line[len("CHECK:"):])
    assert "cube" in info["objects"] and "cam" in info["cameras"] and "lamp" in info["lights"]
    assert info["extra"] == {"smoke": True}
```

- [ ] **Step 6: 실패 확인**

Run: `pytest tests/test_scene_common.py -v`
Expected: FAIL (Blender가 `import common` 실패로 exit code 1 → `CalledProcessError`)

- [ ] **Step 7: common.py 구현**

`pipeline/scenes/common.py`:

```python
"""bpy 전용 헬퍼. Blender 내부 파이썬에서만 import한다(bpy + 표준 라이브러리만 사용)."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motion  # noqa: E402

# 삭제 순서: 오브젝트를 먼저 지워야 나머지 데이터 블록의 사용자 수가 0이 되어 지워진다
_DATA_COLLECTIONS = ("meshes", "materials", "lights", "cameras", "worlds",
                     "node_groups", "particles", "images", "curves")


def parse_scene_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--camera", default="wide")
    p.add_argument("--out", default="")
    p.add_argument("--frame-start", dest="frame_start", type=int, default=1)
    p.add_argument("--frame-end", dest="frame_end", type=int, default=1)
    p.add_argument("--resolution", default="1920x1080")
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--still", action="store_true")
    p.add_argument("--event", default="none")
    p.add_argument("--check", action="store_true")
    argv = sys.argv if argv is None else argv
    rest = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(rest)


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for name in _DATA_COLLECTIONS:
        coll = getattr(bpy.data, name)
        for block in list(coll):
            coll.remove(block)


def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def make_material(name, color, roughness=0.6, metallic=0.0, emission=None,
                  emission_strength=0.0, alpha=1.0, transmission=0.0, ior=1.45):
    mat = bpy.data.materials.new(name)
    p = mat.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1.0)
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Metallic"].default_value = metallic
    p.inputs["IOR"].default_value = ior
    if emission is not None:
        p.inputs["Emission Color"].default_value = (*emission, 1.0)
        p.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        p.inputs["Alpha"].default_value = alpha
        mat.surface_render_method = "BLENDED"
    if transmission > 0.0:
        p.inputs["Transmission Weight"].default_value = transmission
        mat.use_raytrace_refraction = True
    return mat


def _finish(obj, name, material, bevel):
    obj.name = name
    if material is not None:
        obj.data.materials.append(material)
    if bevel > 0.0:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = "ANGLE"
    return obj


def add_box(name, size, location, material, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.scale = size
    # 베벨 폭이 축마다 다르게 늘어나지 않도록 스케일을 메시에 굽는다
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish(obj, name, material, bevel)


def add_cylinder(name, radius, depth, location, material, bevel=0.0, vertices=24, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location,
                                        vertices=vertices, rotation=rotation)
    return _finish(bpy.context.active_object, name, material, bevel)


def add_sphere(name, radius, location, material):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location, segments=32, ring_count=16)
    obj = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _finish(obj, name, material, 0.0)


def add_plane(name, size, location, material, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=size, location=location, rotation=rotation)
    return _finish(bpy.context.active_object, name, material, 0.0)


def add_light(name, kind, location, energy, color, rotation=(0, 0, 0), radius=0.25,
              spot_size=math.radians(90), spot_blend=0.5, volume_factor=1.0):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    data.color = color
    data.use_shadow = True
    data.shadow_soft_size = radius
    data.volume_factor = volume_factor  # 안개 속에서 빛기둥이 보이는 정도
    if kind == "SPOT":
        data.spot_size = spot_size
        data.spot_blend = spot_blend
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    obj.rotation_euler = rotation
    return _link(obj)


def add_camera(name, location, target, lens=35, fstop=2.0, focus_target=None):
    """target 지점을 바라보는 카메라. 초점은 focus_target(오브젝트) 또는 target 지점."""
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.dof.use_dof = True
    data.dof.aperture_fstop = fstop
    cam = _link(bpy.data.objects.new(name, data))
    cam.location = location
    aim = _link(bpy.data.objects.new(f"{name}_target", None))
    aim.location = target
    con = cam.constraints.new("TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    data.dof.focus_object = focus_target if focus_target is not None else aim
    return cam


def keyframe_loop_motion(obj, base, amplitudes, frame_start, frame_end, harmonics=(1, 1, 1)):
    """매 프레임 위치를 키프레임한다. 사인 기반이라 클립 끝과 시작이 이어진다."""
    for frame in range(frame_start, frame_end + 1):
        t = motion.loop_phase(frame, frame_start, frame_end)
        obj.location = tuple(
            base[i] + motion.loop_offset(t, amplitudes[i], harmonics[i]) for i in range(3)
        )
        obj.keyframe_insert("location", frame=frame)


def setup_world_fog(background, fog_color, density, emission_color, emission_strength,
                    end=80.0, samples=64):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("world")
    scene.world = world
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes["Background"].inputs["Color"].default_value = (*background, 1.0)
    vol = nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = density
    vol.inputs["Color"].default_value = (*fog_color, 1.0)
    vol.inputs["Emission Color"].default_value = (*emission_color, 1.0)
    vol.inputs["Emission Strength"].default_value = emission_strength
    links.new(vol.outputs["Volume"], nodes["World Output"].inputs["Volume"])
    ev = scene.eevee
    ev.volumetric_tile_size = "4"
    ev.volumetric_samples = samples
    ev.use_volumetric_shadows = True
    ev.volumetric_end = end
    return world


def _setup_glare(scene, threshold, strength, size):
    ng = bpy.data.node_groups.new("compositor", "CompositorNodeTree")
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    layers = ng.nodes.new("CompositorNodeRLayers")
    glare = ng.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Threshold"].default_value = threshold
    glare.inputs["Strength"].default_value = strength
    glare.inputs["Size"].default_value = size
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(layers.outputs["Image"], glare.inputs["Image"])
    ng.links.new(glare.outputs["Image"], out.inputs["Image"])


def setup_render(resolution, fps, frame_start, frame_end, samples,
                 glare_threshold=1.0, glare_strength=0.25, glare_size=0.6):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = frame_start, frame_end
    scene.eevee.taa_render_samples = samples
    scene.eevee.use_raytracing = True  # 물웅덩이·젖은 바닥 반사
    scene.eevee.use_shadows = True
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass  # 룩 이름이 없는 빌드에서는 기본 룩으로 둔다
    _setup_glare(scene, glare_threshold, glare_strength, glare_size)


def render_still(out_path, frame):
    scene = bpy.context.scene
    scene.frame_set(frame)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)


def render_animation(out_path):
    scene = bpy.context.scene
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "PERC_LOSSLESS"  # 중간 산출물: 조립 때 다시 인코딩한다
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(animation=True)


def dump_check(extra=None):
    scene = bpy.context.scene
    info = {
        "objects": sorted(o.name for o in bpy.data.objects),
        "cameras": sorted(o.name for o in bpy.data.objects if o.type == "CAMERA"),
        "lights": sorted(o.name for o in bpy.data.objects if o.type == "LIGHT"),
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "extra": extra or {},
    }
    print("CHECK:" + json.dumps(info))


def run_scene(build, params):
    """장면 스크립트의 공통 main. build(params, frame_start, frame_end, event) -> {카메라이름: 오브젝트}."""
    args = parse_scene_args()
    resolution = tuple(int(v) for v in args.resolution.split("x"))
    clear_scene()
    setup_render(resolution, args.fps, args.frame_start, args.frame_end, args.samples, **params["glare"])
    cameras = build(params, args.frame_start, args.frame_end, args.event)
    if args.camera not in cameras:
        raise RuntimeError(f"카메라 {args.camera!r}가 없습니다. 가능: {sorted(cameras)}")
    bpy.context.scene.camera = cameras[args.camera]
    if args.check:
        dump_check({"event": args.event, "camera": args.camera})
    elif args.still:
        render_still(Path(args.out), args.frame_start)
    else:
        render_animation(Path(args.out))
```

- [ ] **Step 8: 통과 확인**

Run: `pytest tests/test_scene_common.py tests/test_motion.py -v`
Expected: 6 PASS (Blender 기동 2회, 약 20초)

- [ ] **Step 9: 커밋**

```bash
git add pipeline/scenes tests/test_motion.py tests/bpy_scripts tests/test_scene_common.py
git commit -m "장면 공통 헬퍼: 루프 수학, bpy 재질·도형·조명·카메라·안개·글레어 헬퍼와 스모크 테스트"
```

---

### Task 2: 정류장 지오메트리와 CLI 골격

**Files:**
- Create: `pipeline/scenes/bus_stop.py`, `pipeline/render_shot.py`
- Create: `tests/test_render_shot.py`, `tests/test_bus_stop_scene.py`

**Interfaces:**
- Consumes: Task 1의 `common.*`, `motion.*`.
- Produces:
  - `bus_stop.PARAMS: dict`, `bus_stop.build(params, frame_start, frame_end, event) -> dict[str, obj]` (카메라 이름: `wide`, `shelter`, `marble`, `puddle`)
  - `render_shot.render_clip(scene, camera, out_path, *, frame_start=1, frame_end=1, resolution=(1920,1080), fps=24, samples=64, still=False, event="none") -> Path` (재실행 안전: 산출물이 있으면 건너뜀)
  - `render_shot.check_scene(scene, camera="wide", event="none", frame_end=4) -> dict`
  - `render_shot.scene_script(scene) -> Path`

- [ ] **Step 1: render_shot.py의 실패하는 테스트 작성** — `tests/test_render_shot.py`

```python
from pathlib import Path

import pytest

from pipeline.render_shot import check_scene, render_clip, scene_script


def test_scene_script_rejects_unknown_scene():
    with pytest.raises(FileNotFoundError):
        scene_script("no_such_scene")


def test_check_scene_reports_bus_stop_objects():
    info = check_scene("bus_stop", camera="wide")
    for name in ("road", "sidewalk", "lamp_post", "lamp_head", "bench_seat", "sign_board",
                 "bin", "marble", "shelter_roof"):
        assert name in info["objects"], name
    assert {"wide", "shelter", "marble", "puddle"} <= set(info["cameras"])


def test_render_clip_still_is_idempotent(tmp_path):
    out = tmp_path / "wide.png"
    first = render_clip("bus_stop", "wide", out, resolution=(160, 90), samples=4, still=True)
    assert first.exists()
    mtime = first.stat().st_mtime
    second = render_clip("bus_stop", "wide", out, resolution=(160, 90), samples=4, still=True)
    assert second == first and second.stat().st_mtime == mtime
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_render_shot.py -v`
Expected: FAIL (`ModuleNotFoundError: pipeline.render_shot`)

- [ ] **Step 3: render_shot.py 구현**

```python
"""venv 쪽 렌더 러너: pipeline/scenes/<scene>.py를 헤드리스 Blender로 실행한다.

bpy를 import하지 않는다. 장면 스크립트와는 CLI 인자와 파일로만 통신한다.
"""

import json
import subprocess
import sys
from pathlib import Path

from pipeline.config import BLENDER_BIN, PROJECT_ROOT

SCENES_DIR = PROJECT_ROOT / "pipeline" / "scenes"


def scene_script(scene: str) -> Path:
    path = SCENES_DIR / f"{scene}.py"
    if not path.exists():
        raise FileNotFoundError(f"장면 스크립트가 없습니다: {path}")
    return path


def _base_cmd(scene: str) -> list[str]:
    return [BLENDER_BIN, "--background", "--python-exit-code", "1",
            "--python", str(scene_script(scene)), "--"]


def render_clip(scene: str, camera: str, out_path, *, frame_start=1, frame_end=1,
                resolution=(1920, 1080), fps=24, samples=64, still=False, event="none") -> Path:
    out_path = Path(out_path).resolve()
    if out_path.exists():  # 재실행 안전: 밤새 렌더가 중간에 죽어도 같은 명령으로 이어 간다
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _base_cmd(scene) + [
        "--camera", camera, "--out", str(out_path),
        "--frame-start", str(frame_start), "--frame-end", str(frame_end),
        "--resolution", f"{resolution[0]}x{resolution[1]}",
        "--fps", str(fps), "--samples", str(samples), "--event", event,
    ]
    if still:
        cmd.append("--still")
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
    if not out_path.exists():
        raise RuntimeError(f"렌더가 산출물을 만들지 못했습니다: {out_path}")
    return out_path


def check_scene(scene: str, camera="wide", event="none", frame_end=4) -> dict:
    cmd = _base_cmd(scene) + ["--camera", camera, "--event", event,
                              "--frame-end", str(frame_end), "--check"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=PROJECT_ROOT)
    for line in proc.stdout.splitlines():
        if line.startswith("CHECK:"):
            return json.loads(line[len("CHECK:"):])
    raise RuntimeError(f"CHECK 출력이 없습니다:\n{proc.stdout[-2000:]}")


if __name__ == "__main__":
    # 예: python -m pipeline.render_shot bus_stop wide out.png --still
    scene, camera, out = sys.argv[1:4]
    print(render_clip(scene, camera, out, resolution=(960, 540), samples=16,
                      still="--still" in sys.argv))
```

- [ ] **Step 4: bus_stop.py 지오메트리 구현 (조명·안개는 Task 3에서)**

`pipeline/scenes/bus_stop.py`:

```python
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
    common.add_sphere("marble", 0.08, (0.3, 5.0, 0.53 + 0.08), marble)
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
    marble = bpy.data.objects["marble"]
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
```

- [ ] **Step 5: 통과 확인**

Run: `pytest tests/test_render_shot.py -v`
Expected: 3 PASS. 스틸은 아직 조명이 없어 어둡지만 파일은 만들어진다.

- [ ] **Step 6: 정류장 장면 전용 테스트 작성** — `tests/test_bus_stop_scene.py`

```python
from pipeline.render_shot import check_scene


def test_bus_stop_has_no_bus_without_event():
    info = check_scene("bus_stop", camera="wide", event="none")
    assert not any(n.startswith("bus_") for n in info["objects"])
    assert info["extra"]["camera"] == "wide"


def test_bus_stop_frame_range_is_respected():
    info = check_scene("bus_stop", camera="puddle", frame_end=12)
    assert info["frame_start"] == 1 and info["frame_end"] == 12
```

Run: `pytest tests/test_bus_stop_scene.py -v` → Expected: 2 PASS

- [ ] **Step 7: 커밋**

```bash
git add pipeline/scenes/bus_stop.py pipeline/render_shot.py tests/test_render_shot.py tests/test_bus_stop_scene.py
git commit -m "정류장 지오메트리와 렌더 러너: 도형 기반 장면 골격, CLI 계약, 체크 덤프"
```

---

### Task 3: 조명·안개·비 → 관문 1 (스틸 한 장)

**Files:**
- Modify: `pipeline/scenes/bus_stop.py` (`build_lighting`, `build_rain` 추가, `build` 갱신)
- Modify: `tests/test_bus_stop_scene.py` (밝기 테스트 추가)

**Interfaces:**
- Consumes: Task 2의 `build`, `PARAMS`.
- Produces: `bus_stop.build_lighting(p, frame_start, frame_end)`, `bus_stop.build_rain(p, frame_start, frame_end)`. 체크 덤프의 `lights`에 `lamp_spot`, `lamp_fill`, `moon`이 들어간다.

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_bus_stop_scene.py`에 덧붙임

```python
from PIL import Image

from pipeline.render_shot import render_clip


def test_bus_stop_lights_exist():
    info = check_scene("bus_stop", camera="wide")
    assert {"lamp_spot", "lamp_fill", "moon"} <= set(info["lights"])
    assert "rain_emitter" in info["objects"]


def test_wide_still_is_lit_but_not_blown_out(tmp_path):
    out = render_clip("bus_stop", "wide", tmp_path / "wide.png", resolution=(320, 180), samples=8, still=True)
    img = Image.open(out).convert("L")
    mean = sum(img.getdata()) / (320 * 180)
    assert 3 < mean < 140, mean  # 밤 장면: 검지 않되 어둡다
```

Run: `pytest tests/test_bus_stop_scene.py -v` → Expected: 새 테스트 2개 FAIL

- [ ] **Step 2: 조명·안개·비 구현** — `bus_stop.py`에 추가하고 `build`를 갱신

```python
def build_lighting(p, frame_start, frame_end):
    pal, lamp = p["palette"], p["lamp"]
    spot = common.add_light("lamp_spot", "SPOT", (3.5, 4.2, 4.4), lamp["energy"], pal["amber"],
                            radius=0.35, spot_size=math.radians(lamp["spot_size_deg"]), spot_blend=lamp["blend"])
    common.add_light("lamp_fill", "POINT", (3.5, 4.2, 4.3), lamp["fill_energy"], pal["amber"], radius=0.5, volume_factor=0.0)
    rot = tuple(math.radians(v) for v in p["moon"]["rotation_deg"])
    common.add_light("moon", "SUN", (0, 0, 20), p["moon"]["energy"], pal["moon"], rotation=rot, radius=0.05, volume_factor=0.3)
    # 가로등 깜박임: 주기 함수라 클립을 이어 붙여도 끊기지 않는다
    for frame in range(frame_start, frame_end + 1):
        t = motion.loop_phase(frame, frame_start, frame_end)
        spot.data.energy = lamp["energy"] * motion.flicker_factor(t, lamp["flicker_dips"])
        spot.data.keyframe_insert("energy", frame=frame)
    fog = p["fog"]
    common.setup_world_fog(pal["night"], pal["fog"], fog["density"], fog["emission"], fog["emission_strength"],
                           end=fog["end"], samples=fog["samples"])


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


def build(params, frame_start, frame_end, event):
    build_ground_and_road(params)
    build_shelter(params)
    build_lamp_and_props(params)
    build_background(params)
    build_puddles(params)
    build_lighting(params, frame_start, frame_end)
    build_rain(params, frame_start, frame_end)
    return build_cameras(params, frame_start, frame_end)
```

- [ ] **Step 3: 통과 확인**

Run: `pytest tests/test_bus_stop_scene.py tests/test_render_shot.py -v` → Expected: 전부 PASS

- [ ] **Step 4: 1080p 스틸을 뽑아 사용자에게 보여 준다 (관문 1 시작)**

```bash
source .venv/bin/activate
python - <<'EOF'
from pipeline.render_shot import render_clip
print(render_clip("bus_stop", "wide", "episodes/dream-bus-stop/renders/gate1_wide.png", samples=64, still=True))
EOF
```

이미지를 직접 열어(Read 도구) 확인하고, 경로를 사용자에게 알린다. 함께 확인할 항목:
- 가로등이 화면 안에 있고 안개 속에 빛기둥이 보이는가
- 물웅덩이에 가로등이 비치는가
- 유리구슬이 벤치 위에서 반짝이는가
- 배경 실루엣이 안개에 잠기며 멀어지는가
- 전체가 남청색·호박색·회색 세 색 안에 있는가

- [ ] **Step 5: MCP 뷰포트로 반복 수정한다**

사용자가 수정을 요청하면 `PARAMS`나 `build_*`를 고친 뒤, 열려 있는 Blender에 아래 코드를 `execute_blender_code`로 실행해 즉시 확인한다(렌더 없이 뷰포트 렌더 셰이딩으로 본다).

```python
import sys, importlib
sys.path.insert(0, "/Users/arden/code/vanished-worlds/pipeline/scenes")
import common, motion, bus_stop
for m in (motion, common, bus_stop):
    importlib.reload(m)
common.clear_scene()
common.setup_render((1920, 1080), 24, 1, 48, 64, **bus_stop.PARAMS["glare"])
cams = bus_stop.build(bus_stop.PARAMS, 1, 48, "none")
import bpy
bpy.context.scene.camera = cams["wide"]
bpy.context.scene.frame_set(24)
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces[0].shading.type = "RENDERED"
        area.spaces[0].region_3d.view_perspective = "CAMERA"
```

그다음 `get_viewport_screenshot`으로 확인한다. 뷰포트와 최종 렌더는 글레어·샘플 수가 달라 인상이 조금 다르므로, 큰 방향이 잡히면 Step 4의 1080p 스틸을 다시 뽑아 최종 확인한다. `gate1_wide.png`는 렌더 전에 삭제해야 다시 렌더된다(재실행 안전 규칙).

- [ ] **Step 6: 관문 1 승인 후 커밋**

사용자가 "예쁘다/다음"이라고 답하면 확정된 `PARAMS`로 커밋한다.

```bash
git add pipeline/scenes/bus_stop.py tests/test_bus_stop_scene.py
git commit -m "정류장 조명·안개·비 구현, 관문 1(스틸) 사용자 승인 값 반영"
```

---

### Task 4: 움직임 검증 → 관문 2 (10초 영상, 렌더 시간 실측)

**Files:**
- Modify: `tests/test_bus_stop_scene.py` (짧은 애니메이션 테스트 추가)

**Interfaces:**
- Consumes: Task 2의 `render_clip` (still=False 경로), Task 3의 장면.
- Produces: 실측 프레임당 렌더 시간(초). Task 8의 `shots.json` 샘플 수와 클립 길이를 정하는 근거.

- [ ] **Step 1: 실패하는 테스트 추가**

```python
def test_short_animation_writes_mp4(tmp_path):
    out = render_clip("bus_stop", "wide", tmp_path / "wide.mp4", frame_start=1, frame_end=6,
                      resolution=(160, 90), fps=12, samples=4)
    assert out.exists() and out.stat().st_size > 5_000
```

Run: `pytest tests/test_bus_stop_scene.py::test_short_animation_writes_mp4 -v`
Expected: 처음부터 PASS할 수 있다. 통과하면 그대로 두고 다음 단계로 간다(이 태스크의 목적은 회귀 방지와 실측이다). FAIL이면 `render_animation`의 ffmpeg 설정을 확인한다.

- [ ] **Step 2: 10초 1080p 영상 렌더와 시간 실측**

```bash
source .venv/bin/activate
rm -f episodes/dream-bus-stop/renders/gate2_wide_10s.mp4
/usr/bin/time -p python - <<'EOF'
from pipeline.render_shot import render_clip
print(render_clip("bus_stop", "wide", "episodes/dream-bus-stop/renders/gate2_wide_10s.mp4",
                  frame_start=1, frame_end=240, samples=64))
EOF
```

`real` 초를 240으로 나눠 프레임당 시간을 구한다. 기준은 1.5초 이하다. 넘으면 `PARAMS["fog"]["samples"]`를 48로, 그래도 넘으면 `samples`를 48로 낮춰 다시 잰다. 실측값을 이 계획 파일의 아래 표에 적는다.

| 항목 | 값 |
|---|---|
| 프레임당 렌더 시간(1080p, 64샘플) | (실측 후 기록) |
| 14,000프레임 예상 소요 | (실측 후 기록) |

- [ ] **Step 3: 사용자 확인 (관문 2)**

영상 경로를 알리고 확인 항목을 함께 전달한다: 카메라 움직임이 너무 빠르거나 느리지 않은가, 빗줄기가 자연스러운가, 깜박임이 거슬리지 않는가. 수정 요청은 `PARAMS["cameras"]["wide"]["amplitudes"]`, `PARAMS["rain"]`, `PARAMS["lamp"]["flicker_dips"]`로 반영한다.

- [ ] **Step 4: 승인 후 커밋**

```bash
git add tests/test_bus_stop_scene.py pipeline/scenes/bus_stop.py docs/superpowers/plans/2026-09-02-nameless-city-first-episode.md
git commit -m "관문 2 통과: 10초 움직임 검증, 프레임당 렌더 시간 실측 기록"
```

---

### Task 5: 버스 통과 이벤트와 2분 루프 → 관문 3

**Files:**
- Modify: `pipeline/scenes/bus_stop.py` (`build_bus` 추가, `build`에서 `event == "bus"`일 때 호출)
- Create: `pipeline/assemble.py` (이 태스크에서는 `probe_duration`, `repeat_clip`만)
- Modify: `tests/test_bus_stop_scene.py`
- Create: `tests/test_assemble.py` (repeat_clip 테스트)

**Interfaces:**
- Consumes: `motion.smoothstep`, `common.add_box`, `common.add_light`.
- Produces:
  - `bus_stop.build_bus(p, frame_start, frame_end)`: 빈 오브젝트 `bus`에 차체·창·전조등·미등을 자식으로 붙이고 x를 키프레임한다.
  - `assemble.probe_duration(path) -> float`, `assemble.repeat_clip(clip, out_path, times=2) -> Path`

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_bus_stop_scene.py`에 추가:

```python
def test_bus_event_adds_bus_and_headlights():
    info = check_scene("bus_stop", camera="wide", event="bus", frame_end=8)
    assert {"bus", "bus_body", "bus_tail_l", "bus_tail_r"} <= set(info["objects"])
    assert {"bus_head_l", "bus_head_r"} <= set(info["lights"])
```

`tests/test_assemble.py` 생성:

```python
import math
import subprocess

from pipeline.assemble import probe_duration, repeat_clip


def _color_clip(path, seconds, color="red"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"color=c={color}:s=160x90:r=24:d={seconds}",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_probe_duration(tmp_path):
    clip = _color_clip(tmp_path / "a.mp4", 2)
    assert math.isclose(probe_duration(clip), 2.0, abs_tol=0.1)


def test_repeat_clip_doubles_duration(tmp_path):
    clip = _color_clip(tmp_path / "a.mp4", 2)
    out = repeat_clip(clip, tmp_path / "aa.mp4", times=2)
    assert math.isclose(probe_duration(out), 4.0, abs_tol=0.15)
```

Run: `pytest tests/test_assemble.py tests/test_bus_stop_scene.py::test_bus_event_adds_bus_and_headlights -v`
Expected: FAIL (`pipeline.assemble` 없음, bus 오브젝트 없음)

- [ ] **Step 2: build_bus 구현** — `bus_stop.py`

```python
def build_bus(p, frame_start, frame_end):
    b = p["bus"]
    root = bpy.data.objects.new("bus", None)
    bpy.context.scene.collection.objects.link(root)
    body_mat = common.make_material("bus_body", (0.05, 0.06, 0.08), roughness=0.35)
    body = common.add_box("bus_body", (10.0, 2.6, 3.0), (0, 0, 1.6), body_mat, bevel=0.08)  # 바닥이 도로면(z=0.1)에 닿는다
    win = common.make_material("bus_window", (0.6, 0.55, 0.4), emission=(1.0, 0.85, 0.6), emission_strength=2.0)
    windows = common.add_box("bus_windows", (8.5, 2.64, 1.0), (0.2, 0, 2.3), win, bevel=0.0)
    tail = common.make_material("bus_tail", (0.8, 0.05, 0.02), emission=(1.0, 0.08, 0.03), emission_strength=25.0)
    tail_l = common.add_box("bus_tail_l", (0.05, 0.25, 0.18), (-5.03, 0.9, 1.0), tail, bevel=0.0)
    tail_r = common.add_box("bus_tail_r", (0.05, 0.25, 0.18), (-5.03, -0.9, 1.0), tail, bevel=0.0)
    parts = [body, windows, tail_l, tail_r]
    # 전조등: 진행 방향(+x)을 향하는 스폿. 스폿은 로컬 -Z를 비추므로 Y축 -90도 회전
    for name, y in (("bus_head_l", 0.9), ("bus_head_r", -0.9)):
        parts.append(common.add_light(name, "SPOT", (5.05, y, 1.0), b["headlight_energy"], (1.0, 0.9, 0.7),
                                      rotation=(0, math.radians(-90), 0), radius=0.15,
                                      spot_size=math.radians(50), spot_blend=0.4, volume_factor=1.5))
    for part in parts:
        part.parent = root
    # 등속 통과: smoothstep을 쓰지 않는다(버스는 멈추지 않는다)
    for frame in range(frame_start, frame_end + 1):
        t = (frame - frame_start) / max(frame_end - frame_start, 1)
        root.location = (b["x_start"] + (b["x_end"] - b["x_start"]) * t, b["y"], 0.0)
        root.keyframe_insert("location", frame=frame)


def build(params, frame_start, frame_end, event):
    build_ground_and_road(params)
    build_shelter(params)
    build_lamp_and_props(params)
    build_background(params)
    build_puddles(params)
    build_lighting(params, frame_start, frame_end)
    build_rain(params, frame_start, frame_end)
    if event == "bus":
        build_bus(params, frame_start, frame_end)
    return build_cameras(params, frame_start, frame_end)
```

- [ ] **Step 3: assemble.py 첫 부분 구현**

```python
"""ffmpeg 조립: 클립 길이 조회, 반복, 교차 배열 롱폼 생성."""

import json
import subprocess
from pathlib import Path


def probe_duration(path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(proc.stdout)["format"]["duration"])


def repeat_clip(clip, out_path, times=2) -> Path:
    """클립을 times번 이어 붙인다(재인코딩 없음). 루프 이음새를 눈으로 확인하는 용도."""
    out_path = Path(out_path)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(times - 1),
                    "-i", str(clip), "-c", "copy", str(out_path)], check=True)
    return out_path
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_assemble.py tests/test_bus_stop_scene.py -v` → Expected: 전부 PASS

- [ ] **Step 5: 2분 루프 클립과 버스 클립 렌더, 이음새 확인 파일 생성 (관문 3)**

```bash
source .venv/bin/activate
python - <<'EOF'
from pipeline.render_shot import render_clip
from pipeline.assemble import repeat_clip
loop = render_clip("bus_stop", "wide", "episodes/dream-bus-stop/renders/wide_none.mp4", frame_start=1, frame_end=2880, samples=64)
bus = render_clip("bus_stop", "wide", "episodes/dream-bus-stop/renders/wide_bus.mp4", frame_start=1, frame_end=720, samples=64, event="bus")
print(repeat_clip(loop, "episodes/dream-bus-stop/renders/gate3_wide_x2.mp4"))
print(bus)
EOF
```

(2880프레임은 실측 0.75초 기준 약 36분, 720프레임은 약 9분 걸린다.) 사용자에게 두 파일을 알리고 확인 항목을 전달한다: `gate3_wide_x2.mp4`의 2분 지점에서 카메라·깜박임 이음새가 보이는가, 버스의 전조등 번짐과 통과 속도가 자연스러운가. 빗줄기는 이음새에서 한 번 리셋되지만 빠른 무작위 움직임이라 눈에 띄지 않아야 한다. 띈다면 `PARAMS["rain"]["count"]`를 줄이거나 `lifetime`을 늘린다.

- [ ] **Step 6: 승인 후 커밋**

```bash
git add pipeline/scenes/bus_stop.py pipeline/assemble.py tests/test_assemble.py tests/test_bus_stop_scene.py
git commit -m "버스 통과 이벤트와 루프 이음새 확인 도구, 관문 3(2분 루프) 통과"
```

---

### Task 6: 행성 도입·마무리 장면

**Files:**
- Create: `pipeline/scenes/planet.py`
- Create: `tests/test_planet_scene.py`

**Interfaces:**
- Consumes: `common.*`, `motion.smoothstep`.
- Produces: `planet.PARAMS`, `planet.build(params, frame_start, frame_end, event)` (카메라 이름 `main`, 이벤트 `descend`/`ascend`).

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_planet_scene.py`

```python
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
        assert 1 < sum(img.getdata()) / (160 * 90) < 120
```

Run: `pytest tests/test_planet_scene.py -v` → Expected: FAIL (`planet.py` 없음)

- [ ] **Step 2: planet.py 구현**

```python
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
    "camera": {"far": (0.0, -48.0, 9.0), "near": (0.0, -13.5, 2.5), "target": (0.0, 0.0, 0.0), "lens": 40, "fstop": 4.0},
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
```

- [ ] **Step 3: 통과 확인**

Run: `pytest tests/test_planet_scene.py -v` → Expected: 2 PASS

- [ ] **Step 4: 1080p 스틸을 뽑아 사용자에게 보여 준다**

```bash
python - <<'EOF'
from pipeline.render_shot import render_clip
print(render_clip("planet", "main", "episodes/dream-bus-stop/renders/planet_far.png", frame_start=1, frame_end=480, samples=64, still=True, event="descend"))
# 근접 컷: 스틸은 frame_start 프레임을 렌더하므로, 근접 위치에서 시작하는 ascend로 첫 프레임을 뽑는다
print(render_clip("planet", "main", "episodes/dream-bus-stop/renders/planet_near.png", frame_start=1, frame_end=480, samples=64, still=True, event="ascend"))
EOF
```

관문은 아니지만 행성의 인상(색, 빛점 수, 별 밀도)을 사용자에게 한 번 확인받고 `PARAMS`로 반영한다.

- [ ] **Step 5: 커밋**

```bash
git add pipeline/scenes/planet.py tests/test_planet_scene.py
git commit -m "행성 도입·마무리 장면: 별·행성·빛점, descend/ascend 카메라"
```

---

### Task 7: 롱폼 조립 (교차 배열 + 크로스페이드 + 환경음)

**Files:**
- Modify: `pipeline/assemble.py` (`build_sequence`, `assemble` 추가)
- Modify: `tests/test_assemble.py`
- Modify: `.gitignore` (`episodes/*/final/` 추가)

**Interfaces:**
- Consumes: Task 5의 `probe_duration`.
- Produces:
  - `assemble.build_sequence(loop_clips, event_clips, durations, target_s, event_every_s) -> list[Path]`
  - `assemble.assemble(sequence, out_path, *, intro=None, outro=None, ambience=None, xfade_s=2.0, crf=18) -> Path`

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_assemble.py`

```python
from pathlib import Path

from pipeline.assemble import assemble, build_sequence


def test_build_sequence_cycles_loops_and_inserts_events():
    a, b, e = Path("a.mp4"), Path("b.mp4"), Path("e.mp4")
    durations = {a: 10.0, b: 10.0, e: 3.0}
    seq = build_sequence([a, b], [e], durations, target_s=45.0, event_every_s=20.0)
    assert seq[0] == a and seq[1] == b
    assert e in seq
    assert seq.count(e) == 2  # 20초마다 한 번씩
    assert sum(durations[c] for c in seq) >= 45.0


def test_build_sequence_without_events():
    a = Path("a.mp4")
    seq = build_sequence([a], [], {a: 7.0}, target_s=20.0, event_every_s=5.0)
    assert seq == [a, a, a]


def _tone(path, seconds):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=220:duration={seconds}", str(path)], check=True)
    return path


def test_assemble_crossfades_and_adds_audio(tmp_path):
    clips = [_color_clip(tmp_path / f"{c}.mp4", 3, c) for c in ("red", "green", "blue")]
    intro = _color_clip(tmp_path / "intro.mp4", 2, "black")
    outro = _color_clip(tmp_path / "outro.mp4", 2, "black")
    amb = _tone(tmp_path / "amb.wav", 1)
    out = assemble(clips, tmp_path / "final.mp4", intro=intro, outro=outro, ambience=amb, xfade_s=0.5)
    # 5클립 합계 13초, 크로스페이드 4번 × 0.5초 = 11초
    assert math.isclose(probe_duration(out), 11.0, abs_tol=0.3)
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
                             capture_output=True, text=True, check=True).stdout
    assert "audio" in streams and "video" in streams
```

파일 상단 import에 `from pathlib import Path`, `from pipeline.assemble import assemble, build_sequence`를 합친다.

Run: `pytest tests/test_assemble.py -v` → Expected: 새 테스트 3개 FAIL (ImportError)

- [ ] **Step 2: build_sequence와 assemble 구현** — `assemble.py`에 추가

```python
def build_sequence(loop_clips, event_clips, durations, target_s, event_every_s):
    """루프 클립을 순환하며 target_s를 채우고, event_every_s가 지날 때마다 이벤트 클립을 끼운다."""
    loop_clips, event_clips = list(loop_clips), list(event_clips)
    seq, total, since_event, i, e = [], 0.0, 0.0, 0, 0
    while total < target_s:
        clip = loop_clips[i % len(loop_clips)]
        i += 1
        seq.append(clip)
        total += durations[clip]
        since_event += durations[clip]
        if event_clips and since_event >= event_every_s and total < target_s:
            ev = event_clips[e % len(event_clips)]
            e += 1
            seq.append(ev)
            total += durations[ev]
            since_event = 0.0
    return seq


def assemble(sequence, out_path, *, intro=None, outro=None, ambience=None, xfade_s=2.0, crf=18) -> Path:
    """클립들을 xfade로 이어 붙이고 환경음을 깔아 최종 mp4를 만든다. 모든 클립은 같은 해상도·fps여야 한다."""
    clips = [Path(c) for c in ([intro] if intro else []) + list(sequence) + ([outro] if outro else [])]
    durations = [probe_duration(c) for c in clips]
    total = sum(durations) - xfade_s * (len(clips) - 1)

    # 입력(-i)은 전부 출력 옵션(-map, -t 등)보다 앞에 와야 한다.
    # -stream_loop는 바로 다음 -i에만 적용되는 입력 옵션이라 환경음 -i 직전에 둔다.
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for c in clips:
        cmd += ["-i", str(c)]
    if ambience:
        cmd += ["-stream_loop", "-1", "-i", str(ambience)]  # 스트림 인덱스 len(clips)
    filters, prev, offset = [], "[0:v]", 0.0
    for k in range(1, len(clips)):
        offset += durations[k - 1] - xfade_s
        label = f"[v{k}]"
        filters.append(f"{prev}[{k}:v]xfade=transition=fade:duration={xfade_s}:offset={offset:.3f}{label}")
        prev = label
    if len(clips) == 1:
        filters.append("[0:v]copy[v1]")
        prev = "[v1]"
    cmd += ["-filter_complex", ";".join(filters), "-map", prev]

    if ambience:
        fade_out = max(total - 3.0, 0.0)
        cmd += ["-map", f"{len(clips)}:a", "-af", f"afade=t=in:d=3,afade=t=out:st={fade_out:.3f}:d=3",
                "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd += ["-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
    subprocess.run(cmd, check=True)
    return out_path
```

주의: 영상 입력들 뒤에 환경음을 넣었으므로 환경음의 스트림 인덱스는 `len(clips)`이다. xfade는 모든 입력의 해상도·fps·픽셀 포맷이 같아야 하므로, 행성 클립과 정류장 클립을 같은 `resolution`·`fps`로 렌더해야 한다(`run_episode.py`가 회차 정의의 값을 두 장면에 똑같이 넘긴다).

- [ ] **Step 3: .gitignore에 최종 산출물 폴더 추가**

```bash
printf 'episodes/*/final/\n' >> .gitignore
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_assemble.py -v` → Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add pipeline/assemble.py tests/test_assemble.py .gitignore
git commit -m "롱폼 조립: 교차 배열 시퀀스, xfade 크로스페이드, 환경음 루프와 페이드"
```

---

### Task 8: 회차 실행기와 30분 완성본 → 관문 4

**Files:**
- Create: `pipeline/run_episode.py`, `episodes/dream-bus-stop/shots.json`
- Create: `tests/test_run_episode.py`
- Create(사용자 수동): `library/ambience/rain.wav` (CC0 빗소리, 1분 이상)

**Interfaces:**
- Consumes: `render_shot.render_clip`, `assemble.build_sequence`, `assemble.assemble`, `assemble.probe_duration`.
- Produces: `run_episode.run(episode_dir: Path) -> Path` (최종 mp4 경로), CLI `python -m pipeline.run_episode episodes/dream-bus-stop`.

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_run_episode.py`

```python
import json
import math
import subprocess

from pipeline.assemble import probe_duration
from pipeline.run_episode import run


def test_run_episode_end_to_end_tiny(tmp_path):
    ep = tmp_path / "tiny"
    ep.mkdir()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=110:duration=1",
                    str(ep / "amb.wav")], check=True)
    (ep / "shots.json").write_text(json.dumps({
        "scene": "bus_stop",
        "resolution": [160, 90], "fps": 12, "samples": 4,
        "target_minutes": 0.1, "event_every_s": 2.0, "xfade_s": 0.25,
        "ambience": str(ep / "amb.wav"),
        "intro": {"scene": "planet", "camera": "main", "event": "descend", "duration_s": 1},
        "outro": {"scene": "planet", "camera": "main", "event": "ascend", "duration_s": 1},
        "loops": [{"camera": "wide", "duration_s": 1}, {"camera": "marble", "duration_s": 1}],
        "events": [{"camera": "wide", "event": "bus", "duration_s": 1}],
    }))
    out = run(ep)
    assert out.exists()
    assert probe_duration(out) >= 6.0 - 0.5  # 목표 6초 이상을 채우고 크로스페이드로 조금 줄어든다
    # 재실행하면 렌더를 건너뛰고 같은 결과를 낸다
    mtimes = {p: p.stat().st_mtime for p in (ep / "renders").glob("*.mp4")}
    run(ep)
    assert {p: p.stat().st_mtime for p in (ep / "renders").glob("*.mp4")} == mtimes
```

Run: `pytest tests/test_run_episode.py -v` → Expected: FAIL (`pipeline.run_episode` 없음)

- [ ] **Step 2: run_episode.py 구현**

```python
"""회차 정의(shots.json)를 읽어 클립을 전부 렌더하고 롱폼을 조립한다. 재실행 안전."""

import json
import sys
from pathlib import Path

from pipeline.assemble import assemble, build_sequence, probe_duration
from pipeline.config import PROJECT_ROOT
from pipeline.render_shot import render_clip


def _render(shot, spec, renders, default_scene):
    """클립 파일명 규칙: <scene>_<camera>_<event>.mp4. 이미 있으면 render_clip이 건너뛴다."""
    scene = shot.get("scene", default_scene)
    frames = int(shot["duration_s"] * spec["fps"])
    out = renders / f"{scene}_{shot['camera']}_{shot.get('event', 'none')}.mp4"
    return render_clip(scene, shot["camera"], out, frame_start=1, frame_end=frames,
                       resolution=tuple(spec["resolution"]), fps=spec["fps"], samples=spec["samples"],
                       event=shot.get("event", "none"))


def run(episode_dir) -> Path:
    episode_dir = Path(episode_dir)
    spec = json.loads((episode_dir / "shots.json").read_text())
    renders = episode_dir / "renders"
    renders.mkdir(exist_ok=True)

    loops = [_render(s, spec, renders, spec["scene"]) for s in spec["loops"]]
    events = [_render(s, spec, renders, spec["scene"]) for s in spec.get("events", [])]
    intro = _render(spec["intro"], spec, renders, spec["scene"]) if spec.get("intro") else None
    outro = _render(spec["outro"], spec, renders, spec["scene"]) if spec.get("outro") else None

    durations = {c: probe_duration(c) for c in loops + events}
    sequence = build_sequence(loops, events, durations, spec["target_minutes"] * 60.0, spec["event_every_s"])

    ambience = spec.get("ambience")
    if ambience:
        ambience = Path(ambience) if Path(ambience).is_absolute() else PROJECT_ROOT / ambience
        if not ambience.exists():
            raise FileNotFoundError(f"환경음 파일이 없습니다: {ambience}")

    minutes = spec["target_minutes"]
    label = f"{minutes:g}min"
    out = episode_dir / "final" / f"{episode_dir.name}_{label}.mp4"
    return assemble(sequence, out, intro=intro, outro=outro, ambience=ambience, xfade_s=spec["xfade_s"])


if __name__ == "__main__":
    print(run(sys.argv[1]))
```

- [ ] **Step 3: 통과 확인**

Run: `pytest tests/test_run_episode.py -v` → Expected: PASS (Blender 5회 기동, 약 1~2분)

- [ ] **Step 4: 첫 회차 정의 작성** — `episodes/dream-bus-stop/shots.json`

```json
{
  "scene": "bus_stop",
  "resolution": [1920, 1080],
  "fps": 24,
  "samples": 64,
  "target_minutes": 30,
  "event_every_s": 300,
  "xfade_s": 2.0,
  "ambience": "library/ambience/rain.wav",
  "intro": {"scene": "planet", "camera": "main", "event": "descend", "duration_s": 20},
  "outro": {"scene": "planet", "camera": "main", "event": "ascend", "duration_s": 20},
  "loops": [
    {"camera": "wide", "duration_s": 150},
    {"camera": "shelter", "duration_s": 150},
    {"camera": "marble", "duration_s": 120},
    {"camera": "puddle", "duration_s": 120}
  ],
  "events": [
    {"camera": "wide", "event": "bus", "duration_s": 30},
    {"camera": "shelter", "event": "bus", "duration_s": 30}
  ]
}
```

Task 5에서 이미 렌더한 `renders/wide_none.mp4`(2880프레임=120초)와 `renders/wide_bus.mp4`는 파일명 규칙이 달라 재사용되지 않는다. 디스크와 시간을 아끼려면 이름을 새 규칙으로 바꾼다:

```bash
cd episodes/dream-bus-stop/renders
mv wide_bus.mp4 bus_stop_wide_bus.mp4
```

(`wide_none.mp4`는 120초라 150초 정의와 다르므로 그대로 두고 새로 렌더한다. 120초로 맞추고 싶으면 `shots.json`의 wide `duration_s`를 120으로 고치고 `mv wide_none.mp4 bus_stop_wide_none.mp4`.)

- [ ] **Step 5: 환경음 준비 (사용자 수동 단계)**

사용자에게 CC0 빗소리 파일을 `library/ambience/rain.wav`로 넣어 달라고 요청한다(예: freesound.org에서 라이선스 CC0로 검색, 1분 이상 길이, wav 또는 mp3. mp3면 `shots.json`의 경로를 그에 맞게 바꾼다). 파일이 준비될 때까지 다른 단계(스틸 확인 등)를 진행하고, 준비되면 다음 단계로 간다. `library/ambience/`는 `.gitignore`에 이미 제외되어 있다.

- [ ] **Step 6: 나머지 카메라 스틸을 먼저 확인한다**

30분 렌더 전에, 아직 사용자가 보지 않은 자리(shelter, marble, puddle)의 1080p 스틸을 한 장씩 뽑아 보여 주고 승인을 받는다. 이 자리들이 마음에 들지 않으면 `PARAMS["cameras"]`를 고친다.

```bash
python - <<'EOF'
from pipeline.render_shot import render_clip
for cam in ("shelter", "marble", "puddle"):
    print(render_clip("bus_stop", cam, f"episodes/dream-bus-stop/renders/gate4_{cam}.png", frame_start=1, frame_end=48, samples=64, still=True))
EOF
```

- [ ] **Step 7: 밤새 렌더와 조립 (관문 4)**

```bash
source .venv/bin/activate
nohup python -m pipeline.run_episode episodes/dream-bus-stop > episodes/dream-bus-stop/run.log 2>&1 &
```

예상 소요: 고유 프레임 약 14,000장 × 실측 프레임당 시간(Task 4 표). 중간에 죽으면 같은 명령을 다시 실행하면 완성된 클립은 건너뛴다. 완료되면 `episodes/dream-bus-stop/final/dream-bus-stop_30min.mp4`가 생긴다. 사용자에게 경로를 알리고, 도입→정류장 전환, 5분마다의 버스, 클립 사이 크로스페이드, 환경음 페이드를 확인받는다.

- [ ] **Step 8: 승인 후 커밋**

```bash
git add pipeline/run_episode.py episodes/dream-bus-stop/shots.json tests/test_run_episode.py
git commit -m "회차 실행기와 첫 회차 정의, 관문 4(30분 완성본) 통과"
```

이 커밋으로 첫 영상이 완성된다. 이후의 자동화(소재 회의, 브리프, Gemma, 업로드)는 설계 문서 8절대로 별도 설계에서 다룬다.
