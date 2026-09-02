"""이미지+깊이맵 → 2.5D 패럴랙스 장면 구축과 렌더.

호출: Blender --background --python parallax_scene.py -- <spec.json> <preview|full>
"""

import json
import math
import sys
from pathlib import Path

import bpy

GRID_SUBDIV = 256
CAM_DIST = 2.2  # 평면(폭 2.0)에서 카메라까지의 기본 거리

# layered 모드: depth_qmid(1=가까움)를 이 거리 범위에 선형 매핑한다
LAYER_DIST_NEAR = 1.6
LAYER_DIST_FAR = 4.5
# 모든 평면에 같은 비율의 여백을 준다. 배율이 같으므로 레이어 정합은 유지되고,
# 화면 밖으로 조금 넘치게 만들어 sway가 있어도 평면 가장자리가 프레임에 들어오지 않는다.
PLANE_MARGIN = 1.08
DEFAULT_N_LAYERS = 3


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    spec = json.loads(Path(argv[0]).read_text())
    return spec, argv[1]


def set_engine(scene):
    prop = scene.render.bl_rna.properties["engine"]
    available = {item.identifier for item in prop.enum_items}
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if engine in available:
            scene.render.engine = engine
            return
    raise RuntimeError(f"Eevee 엔진을 찾지 못했습니다: {available}")


def build_plane(spec):
    image = bpy.data.images.load(str(Path(spec["image"]).resolve()))
    aspect = image.size[0] / image.size[1]

    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=GRID_SUBDIV, y_subdivisions=GRID_SUBDIV, size=2.0, calc_uvs=True
    )
    plane = bpy.context.active_object
    plane.scale = (1.0, 1.0 / aspect, 1.0)

    depth_tex = bpy.data.textures.new("depth", type="IMAGE")
    depth_tex.image = bpy.data.images.load(str(Path(spec["depth"]).resolve()))
    depth_tex.image.colorspace_settings.name = "Non-Color"
    depth_tex.extension = "EXTEND"

    disp = plane.modifiers.new("parallax", "DISPLACE")
    disp.texture = depth_tex
    disp.texture_coords = "UV"
    disp.direction = "Z"
    disp.mid_level = 0.0
    disp.strength = spec["depth_strength"]

    mat = bpy.data.materials.new("source")
    # Blender 5.2: 신규 머티리얼은 이미 use_nodes=True/node_tree 보유 상태로 생성된다.
    # 굳이 대입하면 'Material.use_nodes' DeprecationWarning(6.0 제거 예정)이 뜬다.
    nodes = mat.node_tree.nodes
    nodes.clear()
    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.image = image
    emit = nodes.new("ShaderNodeEmission")
    out = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(tex_node.outputs["Color"], emit.inputs["Color"])
    mat.node_tree.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    plane.data.materials.append(mat)
    return plane


def layers_meta_path(spec):
    """레이어 메타 JSON 위치. pipeline/layers.py의 layers_json_path와 같은 규칙.

    Blender의 파이썬에서는 venv(numpy/cv2)에 의존하는 pipeline 패키지를 import할 수
    없어 규칙을 복제한다. 바꿀 때는 양쪽을 함께 고친다(shot_spec.md 참조).
    """
    image = Path(spec["image"]).resolve()
    n_layers = int(spec.get("n_layers", DEFAULT_N_LAYERS))
    return image.parent / f"{image.stem}_layers{n_layers}" / "layers.json"


def layer_distances(qmids):
    """레이어 중앙 깊이(1=가까움)를 카메라로부터의 거리로 선형 매핑한다.

    관측된 qmid 구간을 [LAYER_DIST_NEAR .. LAYER_DIST_FAR]에 맞춰 늘린다. qmid를
    0..1 그대로 대입하지 않는 이유: 실제 깊이맵의 분포는 대개 멀리 쏠려 있어
    (파일럿 이미지는 0.53/0.21/0.08) 거리 구간의 절반도 못 쓰고, 그러면 레이어 간
    시차가 눈에 띄지 않아 다시 "이미지 확대"로 보인다. 구간 양 끝을 고정하면
    레이어 사이의 상대 간격은 유지한 채 시차를 항상 최대로 쓴다.
    """
    q_near, q_far = max(qmids), min(qmids)
    span = q_near - q_far
    if span < 1e-6:  # 깊이가 평평한 경우: 균등 배치로 물러선다
        step = (LAYER_DIST_FAR - LAYER_DIST_NEAR) / max(len(qmids) - 1, 1)
        return [LAYER_DIST_NEAR + step * i for i in range(len(qmids))]
    reach = LAYER_DIST_FAR - LAYER_DIST_NEAR
    return [LAYER_DIST_NEAR + reach * (q_near - q) / span for q in qmids]


def _layer_material(name, image, alpha_blend):
    mat = bpy.data.materials.new(name)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.extension = "EXTEND"
    emit = nodes.new("ShaderNodeEmission")
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emit.inputs["Color"])

    if not alpha_blend:
        links.new(emit.outputs["Emission"], out.inputs["Surface"])
        return mat

    # Blender 5.2(EEVEE Next)에는 blend_method가 남아 있지만 실제로 쓰이는 것은
    # surface_render_method다. BLENDED가 4.x의 blend_method='BLEND'에 해당한다.
    mat.surface_render_method = "BLENDED"
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(tex.outputs["Alpha"], mix.inputs["Fac"])  # 알파 0 → 투명
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(emit.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def build_layers(spec, cam):
    """깊이 밴드 레이어를 서로 다른 거리의 평면에 올린다.

    카메라 시작 위치에서 모든 평면의 화면 footprint가 같아야 원본 이미지와 동일하게
    합성돼 보인다. 거리 d_i인 평면의 폭을 w_i = w0 × (d_i / d0)로 잡으면 성립한다.
    """
    meta = json.loads(layers_meta_path(spec).read_text())
    layers = meta["layers"]  # 가까운 순

    # 화각 계산을 렌더 종횡비와 무관하게 만든다(가로 센서 기준으로 고정)
    cam.data.sensor_fit = "HORIZONTAL"
    tan_half_fov = (cam.data.sensor_width / 2.0) / cam.data.lens

    distances = layer_distances([float(layer["depth_qmid"]) for layer in layers])

    images = [bpy.data.images.load(str(Path(layer["png"]).resolve())) for layer in layers]
    aspect = images[0].size[0] / images[0].size[1]
    render_x, render_y = spec["resolution"]

    # 기준 레이어(가장 가까운 레이어)에서 프레임을 가로·세로 모두 덮는 폭
    d0 = distances[0]
    frame_w = 2.0 * d0 * tan_half_fov
    frame_h = frame_w * render_y / render_x
    w0 = max(frame_w, frame_h * aspect) * PLANE_MARGIN

    for index, (image, distance) in enumerate(zip(images, distances)):
        width = w0 * distance / d0
        bpy.ops.mesh.primitive_plane_add(
            size=2.0, location=(0.0, 0.0, CAM_DIST - distance)
        )
        plane = bpy.context.active_object
        plane.name = f"layer{index}"
        plane.scale = (width / 2.0, width / aspect / 2.0, 1.0)

        is_farthest = index == len(images) - 1
        plane.data.materials.append(
            _layer_material(f"layer{index}", image, alpha_blend=not is_farthest)
        )

    return CAM_DIST - distances[-1]  # 안개 볼륨이 덮어야 할 최원경 z


def build_fog(spec, far_z):
    if spec.get("fog_density", 0) <= 0:
        return
    # 카메라와 최원경 사이를 모두 덮도록 볼륨을 잡는다
    z_lo, z_hi = far_z - 0.5, CAM_DIST + 1.0
    span = z_hi - z_lo
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, (z_lo + z_hi) / 2))
    cube = bpy.context.active_object
    cube.scale = (max(span, 8.0), max(span, 8.0), span)
    mat = bpy.data.materials.new("fog")
    nodes = mat.node_tree.nodes
    nodes.clear()
    vol = nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = spec["fog_density"]
    out = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    cube.data.materials.append(mat)


def build_camera(spec, frame_end):
    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    move = spec["camera"]
    amplitude, sway = move["amplitude"], move.get("sway", 0.0)
    loop = move.get("loop", False)

    for frame in range(1, frame_end + 1):
        t = (frame - 1) / max(frame_end - 1, 1)
        if loop:
            # 사인 기반: frame 1과 frame_end+1의 위치·속도가 일치해 이어 붙여도 티가 나지 않는다
            z = CAM_DIST - amplitude * (0.5 - 0.5 * math.cos(2 * math.pi * t))
            x = sway * math.sin(2 * math.pi * t)
        else:
            z = CAM_DIST - amplitude * t  # 등속 푸시인
            x = sway * math.sin(math.pi * t)
        cam.location = (x, 0.0, z)
        cam.keyframe_insert("location", frame=frame)
    return cam


def setup_render(spec, mode):
    scene = bpy.context.scene
    set_engine(scene)
    scene.render.resolution_x, scene.render.resolution_y = spec["resolution"]
    scene.render.fps = spec["fps"]
    scene.frame_start = 1
    scene.frame_end = int(spec["duration_s"] * spec["fps"])

    out_dir = Path(spec["out_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "preview":
        scene.frame_set((scene.frame_start + scene.frame_end) // 2)
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(out_dir / f"{spec['name']}_preview.png")
        bpy.ops.render.render(write_still=True)
    else:
        # Blender 5.2: image_settings.media_type을 VIDEO로 먼저 지정해야
        # file_format에 FFMPEG를 대입할 수 있다(브리프의 4.x대 코드에는 없던 단계).
        scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
        scene.render.filepath = str(out_dir / f"{spec['name']}.mp4")
        bpy.ops.render.render(animation=True)


def main():
    spec, mode = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    frame_end = int(spec["duration_s"] * spec["fps"])
    cam = build_camera(spec, frame_end)
    # mode 미지정 스펙은 v1(단일 평면 부조)이므로 relief로 해석한다
    if spec.get("mode", "relief") == "layered":
        far_z = build_layers(spec, cam)
    else:
        build_plane(spec)
        far_z = 0.0
    build_fog(spec, far_z)
    setup_render(spec, mode)


main()
