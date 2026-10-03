import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
path='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
bp=unreal.load_asset(path)
assert bp
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False),'Blueprint save failed'
print('PUSH_BLUEPRINT_SAVED',path)
