import bpy
import json
import sys


fbx_path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx_path)

needles = (
    "upperarm_l_CONTROL",
    "lowerarm_l_CONTROL",
    "hand_l_CONTROL",
    "upperarm_r_CONTROL",
    "lowerarm_r_CONTROL",
    "hand_r_CONTROL",
)


def iter_fcurves(action):
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        yield from legacy
        return
    for layer in getattr(action, "layers", ()):
        for strip in getattr(layer, "strips", ()):
            for channelbag in getattr(strip, "channelbags", ()):
                yield from channelbag.fcurves

objects = {}
for obj in bpy.data.objects:
    if any(needle in obj.name for needle in needles):
        action = obj.animation_data.action if obj.animation_data else None
        curves = []
        if action:
            for curve in iter_fcurves(action):
                values = [float(k.co.y) for k in curve.keyframe_points]
                default = 1.0 if curve.data_path == "scale" else 0.0
                if any(abs(value - default) > 1.0e-7 for value in values):
                    curves.append({
                        "path": curve.data_path,
                        "index": curve.array_index,
                        "first": values[0],
                        "minimum": min(values),
                        "maximum": max(values),
                    })
        objects[obj.name] = {
            "action": action.name if action else None,
            "curves": curves,
        }

actions = {}
for action in bpy.data.actions:
    if any(needle in action.name for needle in needles):
        changed = []
        for curve in iter_fcurves(action):
            values = [float(k.co.y) for k in curve.keyframe_points]
            default = 1.0 if curve.data_path == "scale" else 0.0
            if any(abs(value - default) > 1.0e-7 for value in values):
                changed.append({
                    "path": curve.data_path,
                    "index": curve.array_index,
                    "first": values[0],
                    "minimum": min(values),
                    "maximum": max(values),
                })
        actions[action.name] = changed

print("CONTROL_FBX_ACTIONS=" + json.dumps({"objects": objects, "actions": actions}, sort_keys=True))
