import unreal,builtins,json
s=builtins._blood_visual;w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world();actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor)
managers=[a for a in actors if isinstance(a,unreal.ProphecyBloodTexturePaintManager)];decals=[a for a in actors if 'A_DecalManager_C'==a.get_class().get_name()];swords=[a for a in actors if 'A_Sword_C'==a.get_class().get_name()]
assert len(managers)==len(decals)==1
m=managers[0];d=decals[0];assert d.get_editor_property('paint manager')==m;assert d.get_editor_property('floor')
r={'manager':m.get_path_name(),'manager_count':len(managers),'decal_manager':d.get_path_name(),'decal_count':len(decals),'floor':d.get_editor_property('floor').get_path_name(),'auto_generation':m.editor_auto_create_blood_materials,'pair_count':len(m.blood_enabled_material_pairs),'swords':[]}
for a in swords:
 ref=a.get_editor_property('decal manager');assert ref==d
 r['swords'].append({'actor':a.get_path_name(),'decal_manager':ref.get_path_name()})
(s['out']/'production-verified.json').write_text(json.dumps(r,indent=2));print(r)
