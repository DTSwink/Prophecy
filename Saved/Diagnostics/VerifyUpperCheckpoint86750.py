import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('UPPER86750_PIE_ACTIVE', bool(editor.get_game_world()))
enum = unreal.find_object(None, '/Script/GameAnimationSample3.EProphecyUpperCheckpoint')
assert enum, 'Upper picker enum not loaded'
enum_type = unreal.get_type_from_enum(enum)
print('UPPER86750_ENUM_TYPE', enum_type)
entries = [(entry.name, int(entry.value), str(entry.get_display_name())) for entry in enum_type]
print('UPPER86750_ENUM_ENTRIES', entries)
assert any(value == 3 and label == 'October 1 - Hand Velocity Bound (86750)'
           for name, value, label in entries), entries
for name in ['SetUpperCheckpoint', 'GetUpperCheckpoint']:
    assert unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyUpperCheckpointLibrary:' + name), name
if not editor.get_game_world():
    blueprint = unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
    assert blueprint
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    print('UPPER86750_POSE_BLUEPRINT_COMPILED_WITHOUT_SAVING')
else:
    print('UPPER86750_USER_PLAY_PRESERVED_BLUEPRINT_COMPILE_DEFERRED')
print('UPPER86750_REFLECTION_VERIFIED')
