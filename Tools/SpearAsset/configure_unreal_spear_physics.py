import os,pathlib,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
bp=unreal.load_asset('/Game/_mygame/spear/A_Spear')
ss=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
for h in ss.k2_gather_subobject_data_for_blueprint(bp):
    obj=unreal.SubobjectDataBlueprintFunctionLibrary.get_object(unreal.SubobjectDataBlueprintFunctionLibrary.get_data(h))
    if obj.get_name()=='sword_GEN_VARIABLE':
        body=obj.get_editor_property('body_instance')
        body.set_editor_property('use_macd',False)
        body.set_editor_property('use_ccd',True)
        obj.set_editor_property('body_instance',body)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
print('Spear uses supported linear-cast CCD, with MACD disabled.')
