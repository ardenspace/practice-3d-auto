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


def build_fog(spec):
    if spec.get("fog_density", 0) <= 0:
        return
    bpy.ops.mesh.primitive_cube_add(size=4.0, location=(0, 0, CAM_DIST / 2))
    cube = bpy.context.active_object
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
    build_plane(spec)
    build_fog(spec)
    build_camera(spec, frame_end)
    setup_render(spec, mode)


main()
