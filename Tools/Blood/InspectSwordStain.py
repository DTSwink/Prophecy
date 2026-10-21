import json,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w=ed.get_game_world() or ed.get_editor_world()
r={'play':bool(ed.get_game_world()),'swords':[],'materials':[]}
for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
    if a.get_class().get_name()=='A_Sword_C':
        c=a.get_editor_property('sword');m=c.get_material(0)
        r['swords'].append({'actor':a.get_path_name(),'material':m.get_path_name(),'class':m.get_class().get_name()})
for p in unreal.EditorAssetLibrary.list_assets('/Game/Prophecy/BloodTexturePainting/Generated',recursive=True):
    if 'sword' in p.lower():
        m=unreal.load_asset(p)
        r['materials'].append({'path':p,'scalar':[str(n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(m)],'texture':[str(n) for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(m)]})
print(json.dumps(r))
