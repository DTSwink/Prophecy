"""Save verified leaf-pommel delivery and close only the task-owned Blender."""
import bpy,json
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
source=bpy.data.scenes['Scene'];game=bpy.data.scenes['GAME • Unreal export']
audit=json.loads((OUT/'Pommel_Leaf_Verification.json').read_text(encoding='utf-8'))
verified=json.loads((OUT/'Export_Verification.json').read_text(encoding='utf-8'))
assert audit['status']=='LEAF_POMMEL_SOURCE_AND_ACTUAL_GAME_COLLISION_AUDITED'
assert verified['triangles']==audit['source_game_comparison']['source_triangles']==len(game.objects['SM_ImperialSpear'].data.polygons)
assert verified['fbx_hulls']==game['CollisionHullCount']==17
assert audit['wood_joint']['outside_samples']==0
assert not any(s.name.startswith('TEMP') for s in bpy.data.scenes)
image_paths={im:Path(bpy.path.abspath(im.filepath)).resolve() for im in bpy.data.images if im.source=='FILE' and im.filepath}
assert all(p.is_file() for p in image_paths.values())
source['Spear_revision']='08: selected flattened leaf pommel; accepted remaining spear preserved'
source['PommelDesign']='flattened_leaf'
source['Pommel_concept_accepted']=True
source['Pommel_model_appearance_accepted']=False
source['Unreal_validated']=False
for scene,filename in [(game,'ImperialSpear_Game.blend'),(source,'ImperialSpear_Source.blend')]:
    bpy.context.window.scene=scene;bpy.ops.object.select_all(action='DESELECT')
    for im,path in image_paths.items():im.filepath=bpy.path.relpath(str(path),start=str(OUT))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/filename),relative_remap=False)
for im,path in image_paths.items():im.filepath=str(path)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/PommelLeaf/Working.blend'))
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print('Verified leaf pommel saved to source/game and working checkpoints; closing owned Blender.')
bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender(),first_interval=2)
