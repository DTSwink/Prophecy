import unreal
e=unreal.load_object(None,'/Script/GameAnimationSample3.EProphecyAttackCheckpoint')
print('CANONICAL_ENUM',e)
print('FRESH_ENUM_TYPE',unreal.get_type_from_enum(e))
print('FRESH_ENUM_CHOICES',list(unreal.get_type_from_enum(e)))
print('BLUEPRINT_REFRESH_METHODS',[x for x in dir(unreal.BlueprintEditorLibrary) if 'refresh' in x or 'node' in x])
