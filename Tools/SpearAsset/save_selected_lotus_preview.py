"""Preserve the exact live pommel selected in the user's latest screenshot."""
import bpy,json
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');W=R/'Saved/Diagnostics/ImperialSpear/PommelLotus'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s
art=bpy.data.collections['SPEAR • editable components']
assert len(art.objects['02 • carved lotus pommel body'].data.vertices)==8322
assert len(art.objects['Pommel • six carved lotus petals'].data.vertices)==3890
assert bpy.data.materials['M_ImperialSpear_PBR'].get('PommelCavityGate')=='COLOR_R_GT_0.01'
s['Pommel_model_appearance_accepted']=True;s['Pommel_selected_preview']='Gold_reference.png; user screenshot c4f1748f, October28'
for im in bpy.data.images:
    if im.source=='FILE' and im.filepath:im.filepath=bpy.path.abspath(im.filepath)
bpy.ops.wm.save_as_mainfile(filepath=str(W/'Selected_Pommel_Preview.blend'))
bpy.ops.wm.save_as_mainfile(filepath=str(W/'Working.blend'))
(W/'Selected_Preview_Status.json').write_text(json.dumps({'status':'USER_SELECTED_VISUAL_VERSION','source':str(W/'Selected_Pommel_Preview.blend'),'reference_preview':str(W/'Gold_reference.png'),'body_vertices':8322,'bud_vertices':3890,'export_refresh_complete':False,'note':'Current source frozen to the user-selected image. Partial export attempt stopped on LOD color range; final exports still require refresh and readback.'},indent=2))
print('Exact user-selected pommel preserved; no geometry changes applied.')
