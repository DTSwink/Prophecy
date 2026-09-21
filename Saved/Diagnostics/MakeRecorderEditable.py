import unreal
print([n for n in dir(unreal.BlueprintEditorLibrary) if 'variable' in n])
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
for name in ['RecordingInput','PlayingInput','RecordingSlot','ReplayedInput']:
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp,name,True)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
