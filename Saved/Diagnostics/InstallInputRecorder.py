import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Debug.InstallInputRecorder')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
cdo=unreal.get_default_object(bp.generated_class())
for name in ['RecordingInput','PlayingInput','RecordingSlot','ReplayedInput']:
    print(name,cdo.get_editor_property(name))
