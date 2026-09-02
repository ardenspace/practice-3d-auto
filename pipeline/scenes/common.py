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
                    end=80.0, samples=64, tile_size="4"):
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
    ev.volumetric_tile_size = tile_size  # 낮을수록 froxel 이 촘촘하다. "4"는 빛기둥에 격자 무늬가 남는다
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
