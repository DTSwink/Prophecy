"""Read-only Blender source/export probe; never save the opened blend file."""
import json
import sys
from pathlib import Path
import bpy

OUT = Path(r"C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/BossBindAudit/20260907")
OUT.mkdir(parents=True, exist_ok=True)

def mat(value):
    return [list(row) for row in value]

def probe(label):
    bpy.context.view_layer.update()
    result = {"file": bpy.data.filepath, "frame": bpy.context.scene.frame_current,
              "unit_scale": bpy.context.scene.unit_settings.scale_length, "objects": []}
    for obj in bpy.data.objects:
        row = {"name": obj.name, "type": obj.type, "hidden": obj.hide_get(),
               "matrix_world": mat(obj.matrix_world), "parent": obj.parent.name if obj.parent else None}
        if obj.type == 'ARMATURE':
            row["pose_position"] = obj.data.pose_position
            row["bones"] = {b.name: {"parent": b.parent.name if b.parent else None,
                "rest_world": mat(obj.matrix_world @ b.matrix_local),
                "pose_world": mat(obj.matrix_world @ obj.pose.bones[b.name].matrix),
                "basis": mat(obj.pose.bones[b.name].matrix_basis), "connected": b.use_connect}
                for b in obj.data.bones}
        elif obj.type == 'MESH':
            row["vertex_count"] = len(obj.data.vertices)
            row["modifiers"] = [{"name": m.name, "type": m.type,
                "rig": m.object.name if m.type == 'ARMATURE' and m.object else None,
                "viewport": m.show_viewport} for m in obj.modifiers]
            if obj.name == 'boss' or label != 'source':
                row["raw_world"] = [list(obj.matrix_world @ v.co) for v in obj.data.vertices]
                ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                em = ev.to_mesh()
                row["evaluated_world"] = [list(ev.matrix_world @ v.co) for v in em.vertices]
                row["polygons"] = [list(p.vertices) for p in em.polygons]
                ev.to_mesh_clear()
                row["weights"] = [{obj.vertex_groups[g.group].name: g.weight for g in v.groups if g.weight > 0}
                                  for v in obj.data.vertices]
                row["materials"] = [s.material.name if s.material else None for s in obj.material_slots]
        result["objects"].append(row)
    (OUT / (label + '.json')).write_text(json.dumps(result), encoding='utf8')
    print('BOSS_BIND_PROBE', label, [(r['name'], r.get('vertex_count')) for r in result['objects'] if r['type'] == 'MESH'])

probe('source')
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=r"C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/BlenderExchange/BossUEFN/SKM_Boss_UEFN.fbx",
    automatic_bone_orientation=False, use_anim=False, ignore_leaf_bones=False)
probe('latest_fbx')
