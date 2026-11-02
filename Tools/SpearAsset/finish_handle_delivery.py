"""Save the final handle/relief pass and shut down only the owned Blender session."""
import bpy,json
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
source=bpy.data.scenes['Scene'];game=bpy.data.scenes['GAME • Unreal export']
verified=json.loads((OUT/'Export_Verification.json').read_text(encoding='utf-8'))
audit=json.loads((OUT/'Handle_Finish_Verification.json').read_text(encoding='utf-8'))
assert verified['triangles']==audit['source_triangles']==len(game.objects['SM_ImperialSpear'].data.polygons)
assert verified['fbx_hulls']==game['CollisionHullCount']
assert not any(s.name.startswith('TEMP') for s in bpy.data.scenes)
image_paths={im:Path(bpy.path.abspath(im.filepath)) for im in bpy.data.images if im.source=='FILE'}
assert all(p.is_file() for p in image_paths.values())
source['Spear_revision']='07: final wood/leather/gold transitions and angular cast S relief'
source['Spearhead_accepted_by_user_before_S_exception']=True
source['Accepted_spearhead_preserved_except_requested_S_relief']=True
source['Appearance_accepted']=False
source['Unreal_validated']=False
for scene,filename in [(game,'ImperialSpear_Game.blend'),(source,'ImperialSpear_Source.blend')]:
    bpy.context.window.scene=scene;bpy.ops.object.select_all(action='DESELECT')
    for im,path in image_paths.items():im.filepath=bpy.path.relpath(str(path),start=str(OUT))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/filename),relative_remap=False)
for im,path in image_paths.items():im.filepath=str(path)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print('Final source/game and working checkpoint saved; accepted camera retained.')
def close_owned():bpy.ops.wm.quit_blender()
bpy.app.timers.register(close_owned,first_interval=2)
