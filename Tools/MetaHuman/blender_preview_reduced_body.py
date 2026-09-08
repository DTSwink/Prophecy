"""Render headless preview stills of the reduced body in UEFN poses.

Run:
  blender --background --python Tools/MetaHuman/blender_preview_reduced_body.py

Loads Body_UEFN78.blend and, per test animation, imports the UEFN animation
FBX (a fully animated UEFN armature with the same rest pose) and points the
mesh's Armature modifier at it. This sidesteps action copying entirely: the
mesh deforms on the animated skeleton exactly as it will in Unreal, because
only shared-bone weights exist after the fold. Output: Saved/BlenderShots/.
"""

import math
import os

import bpy
from mathutils import Matrix, Vector

PROJECT = r"C:\Users\singerie\Documents\Unreal Projects\Prophecy"
EXCHANGE = os.path.join(PROJECT, "Saved", "BlenderExchange")
BLEND = os.path.join(EXCHANGE, "Body_UEFN78.blend")
OUT_DIR = os.path.join(PROJECT, "Saved", "BlenderShots")

# (anim fbx, label, sample times in seconds)
SHOTS = [
    ("Anim_Climb.fbx", "Climb", (2.0, 1.4, 3.1)),
    ("Anim_CliffCatch.fbx", "CliffCatch", (0.6, 1.0)),
    ("Anim_Sprint.fbx", "Sprint", (0.2,)),
    ("Anim_Slide.fbx", "Slide", (0.6,)),
]

FPS = 30


def look_at(camera, target):
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def bone_head_world(armature, bone_name):
    pose_bone = armature.pose.bones.get(bone_name)
    if pose_bone is None:
        raise RuntimeError("Missing bone: " + bone_name)
    return armature.matrix_world @ pose_bone.head


def render(filepath):
    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    print("SHOT|{}".format(filepath))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.75, 0.75, 0.78)
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1400
    scene.render.fps = FPS

    body_arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh_obj = next(o for o in bpy.data.objects if o.type == "MESH")
    body_matrix = body_arm.matrix_world.copy()
    # Mesh offset relative to its rest armature; reapplied against the
    # carrier's animated object transform every frame.
    mesh_relative = body_matrix.inverted() @ mesh_obj.matrix_world.copy()

    # UEFN mannequin as ground-truth comparison: same skeleton, same poses.
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(
        filepath=os.path.join(EXCHANGE, "UEFN_Mannequin.fbx"),
        ignore_leaf_bones=False,
        automatic_bone_orientation=False,
    )
    mannequin_objects = [o for o in set(bpy.data.objects) - before]
    mannequin_meshes = [o for o in mannequin_objects if o.type == "MESH"]
    mannequin_relatives = {
        m.name: body_matrix.inverted() @ m.matrix_world.copy() for m in mannequin_meshes
    }

    camera_data = bpy.data.cameras.new("PreviewCam")
    camera_data.clip_start = 0.01
    camera_data.clip_end = 1000.0
    camera = bpy.data.objects.new("PreviewCam", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    light_data = bpy.data.lights.new("KeyLight", type="SUN")
    light_data.energy = 3.0
    light = bpy.data.objects.new("KeyLight", light_data)
    light.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
    scene.collection.objects.link(light)

    modifier = next(m for m in mesh_obj.modifiers if m.type == "ARMATURE")

    for anim_file, label, times in SHOTS:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(
            filepath=os.path.join(EXCHANGE, anim_file),
            ignore_leaf_bones=False,
            automatic_bone_orientation=False,
        )
        imported = [o for o in set(bpy.data.objects) - before]
        anim_arm = next(o for o in imported if o.type == "ARMATURE")

        # Drive both meshes from the carrier armature.
        modifier.object = anim_arm
        mannequin_modifiers = []
        for m in mannequin_meshes:
            mann_mod = next(mm for mm in m.modifiers if mm.type == "ARMATURE")
            mann_mod.object = anim_arm
            mannequin_modifiers.append(mann_mod)
        for obj in imported:
            obj.hide_render = True
        anim_arm.hide_render = True

        for sample_time in times:
            frame = int(round(sample_time * FPS))
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            # UE root motion lives on the carrier *object*; keep the meshes
            # aligned with it so the Armature modifier binds correctly.
            mesh_obj.matrix_world = anim_arm.matrix_world @ mesh_relative
            for m in mannequin_meshes:
                m.matrix_world = anim_arm.matrix_world @ mannequin_relatives[m.name]
            bpy.context.view_layer.update()

            tag = "{}_{:.1f}s".format(label, sample_time).replace(".", "p")

            head = bone_head_world(anim_arm, "head")
            pelvis = bone_head_world(anim_arm, "pelvis")
            center = (head + pelvis) / 2.0
            print("POSE|{}|head={}|pelvis={}".format(
                tag, tuple(round(v, 2) for v in head), tuple(round(v, 2) for v in pelvis)))

            def render_ab(name_fmt):
                # A = reduced MetaHuman body, B = UEFN mannequin ground truth.
                for m in mannequin_meshes:
                    m.hide_render = True
                mesh_obj.hide_render = False
                render(os.path.join(OUT_DIR, name_fmt.format("Reduced")))
                mesh_obj.hide_render = True
                for m in mannequin_meshes:
                    m.hide_render = False
                render(os.path.join(OUT_DIR, name_fmt.format("Mannequin")))
                for m in mannequin_meshes:
                    m.hide_render = True
                mesh_obj.hide_render = False

            # FBX coordinates remain centimeters in Blender even though the
            # scene unit scale is 0.01.  The old distances (1.7 / 0.45) put the
            # camera inside a ~160-unit-tall body and produced blank gray
            # renders.  Keep all camera offsets in the same centimeter space.
            camera.location = center + Vector((170.0, -170.0, 20.0))
            look_at(camera, center)
            camera_data.lens = 40
            render_ab("{{}}_{}_full.png".format(tag))

            for side in ("r", "l"):
                hand = bone_head_world(anim_arm, "hand_" + side)
                middle = bone_head_world(anim_arm, "middle_01_" + side)
                lower = bone_head_world(anim_arm, "lowerarm_" + side)
                focus = (hand + middle) / 2.0
                # Camera sits perpendicular to the forearm axis so the wrist
                # profile is visible regardless of pose.
                arm_axis = (hand - lower).normalized()
                side_dir = arm_axis.cross(Vector((0.0, 0.0, 1.0)))
                if side_dir.length < 0.3:
                    side_dir = arm_axis.cross(Vector((0.0, 1.0, 0.0)))
                side_dir.normalize()
                for view, direction in (("A", side_dir), ("B", -side_dir)):
                    camera.location = focus + direction * 45.0 + Vector((0.0, 0.0, 12.0))
                    look_at(camera, focus)
                    camera_data.lens = 50
                    render_ab("{{}}_{}_hand{}_{}.png".format(tag, side.upper(), view))

        # Restore the modifier and drop the carrier before the next clip.
        modifier.object = body_arm
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)

    print("PREVIEW_DONE")


main()
