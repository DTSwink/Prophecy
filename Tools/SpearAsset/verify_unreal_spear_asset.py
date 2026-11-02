import os,pathlib,json,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);assert not ed.get_game_world()
bp=unreal.load_asset('/Game/_mygame/spear/A_Spear');cdo=unreal.get_default_object(bp.generated_class())
d=cdo.get_editor_property('velocity cut dampings');assert [d.x,d.y,d.z]==[100,10,1]
assert cdo.get_editor_property('Pike Target Thickness Cm')==15
assert not cdo.get_editor_property('debug mode')
assert cdo.get_editor_property('freeze tick')==-1 and cdo.get_editor_property('unfreeze tick')==0
result={'damping':[d.x,d.y,d.z],'thickness_cm':15,'debug_mode':False,'components':[]}
ss=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);seen=set()
for h in ss.k2_gather_subobject_data_for_blueprint(bp):
    obj=unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h))
    if obj.get_path_name() in seen or obj.get_name()!='sword_GEN_VARIABLE':continue
    seen.add(obj.get_path_name());mesh=obj.get_editor_property('static_mesh');scale=obj.get_editor_property('relative_scale3d')
    body=obj.get_editor_property('body_instance')
    assert not body.get_editor_property('use_macd') and body.get_editor_property('use_ccd')
    assert obj.get_collision_object_type()==unreal.CollisionChannel.ECC_SWORD
    assert obj.get_material(0).get_path_name()=='/Game/_mygame/spear/M_ImperialSpear.M_ImperialSpear'
    result['components'].append({'mesh':mesh.get_path_name(),'scale':[scale.x,scale.y,scale.z],'body':body.export_text(),'material':obj.get_material(0).get_path_name()})
    assert all(abs(a-b)<1e-12 for a,b in zip([scale.x,scale.y,scale.z],[.8623427588789339,.8834927125312151,.7619161867885869]))
assert len(result['components'])==1
assert all(p.get_name()=='/Game/_mygame/spear/A_Spear' for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
# Fixture default edits were restored in memory; persist only the verified copy.
unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=True)
(out/'asset-verified.json').write_text(json.dumps(result,indent=2))
print('Verified saved spear scale, material, CCD, tuning and non-debug defaults.')
