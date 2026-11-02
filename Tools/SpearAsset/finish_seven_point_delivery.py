"""Save verified scenes without moving the matched render camera; close owned Blender."""
import bpy,json
from pathlib import Path

ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT=ROOT/'Exports/ImperialSpear'
source=bpy.data.scenes['Scene'];game=bpy.data.scenes['GAME • Unreal export']
verification=json.loads((OUT/'Export_Verification.json').read_text(encoding='utf-8'))
assert verification['triangles']==len(game.objects['SM_ImperialSpear'].data.polygons)
assert verification['fbx_hulls']==game['CollisionHullCount']
assert not any(scene.name.startswith('TEMP') for scene in bpy.data.scenes)
for image in bpy.data.images:
    if image.source=='FILE':
        absolute=Path(bpy.path.abspath(image.filepath))
        assert absolute.is_file(),str(absolute)
        image.filepath=str(absolute)
source['Spear_revision']='06: seven reported gold-assembly corrections; render and FBX roundtrip reviewed'
source['Appearance_accepted']=False
source['Unreal_validated']=False
for scene,centre,filename in [(game,(.04,0,-.135),'ImperialSpear_Game.blend'),
                              (source,(.04,0,1.1),'ImperialSpear_Source.blend')]:
    bpy.context.window.scene=scene
    bpy.ops.object.select_all(action='DESELECT')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                view=area.spaces.active
                view.region_3d.view_location=centre
                view.region_3d.view_distance=2.55
                view.region_3d.view_rotation=source.camera.rotation_euler.to_quaternion()
                view.region_3d.view_perspective='ORTHO'
                view.shading.type='SOLID';view.overlay.show_floor=False
    for image in bpy.data.images:
        if image.source=='FILE':image.filepath=bpy.path.relpath(bpy.path.abspath(image.filepath),start=str(OUT))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/filename),relative_remap=False)
# Preserve an authoritative resumable checkpoint with correctly remapped paths.
for image in bpy.data.images:
    if image.source=='FILE':image.filepath=bpy.path.abspath(image.filepath)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print('Verified export scenes and current checkpoint saved; matched camera retained.')
def close_owned():bpy.ops.wm.quit_blender()
bpy.app.timers.register(close_owned,first_interval=2)
