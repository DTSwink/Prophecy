"""Open the verified working rig in a useful front, framed viewport."""

import bpy


rig = bpy.data.objects.get("UEFN_WORKING_CLEAN_RIG")
if rig:
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    rig.hide_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")

for area in bpy.context.screen.areas:
    if area.type != "VIEW_3D":
        continue
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    if region is None:
        continue
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.view3d.view_axis(type="FRONT", align_active=False)
        bpy.ops.view3d.view_selected(use_all_regions=False)
