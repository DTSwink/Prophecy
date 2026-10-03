import unreal
base='/Script/GameAnimationSample3.'
cls=unreal.load_class(None,base+'ProphecyUpperCheckpointLibrary')
assert cls, 'Upper picker class not loaded'
print('Upper picker class:', cls.get_path_name())
for name in ['SetUpperCheckpoint','GetUpperCheckpoint']:
    obj=unreal.find_object(None,base+'ProphecyUpperCheckpointLibrary:'+name)
    assert obj, name
    print('Node loaded:',obj.get_path_name())
enum=unreal.find_object(None,base+'EProphecyUpperCheckpoint')
assert enum
print('Enum loaded:',enum.get_path_name())
print('PIE active:',bool(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()))
