import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary'))
assert lib.call_method('SetTemporaryPreDragFixVersion',(None,True)) is False
print('TEMP_PRE_DRAG_NODE_REFLECTED; PLAY_ACTIVE',bool(ed.get_game_world()))
