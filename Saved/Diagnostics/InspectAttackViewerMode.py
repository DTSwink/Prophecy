import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PIE',bool(ed.get_game_world()))
enum=unreal.get_type_from_enum(unreal.load_object(None,'/Script/GameAnimationSample3.EProphecyNNInterpolationMode'))
print('INTERPOLATION_CHOICES',[(x,str(getattr(enum,x))) for x in dir(enum) if x.isupper()])
e=unreal.load_object(None,'/Script/GameAnimationSample3.EProphecyNNInterpolationMode')
helper=unreal.load_object(None,'/Script/Engine.Default__KismetNodeHelperLibrary')
names=[str(helper.call_method('GetEnumeratorName',args=(e,i))) for i in range(4)]
print('NATIVE_ENUM',names)
assert names[2].endswith('AttackViewer')
print('ATTACK_VIEWER_REFLECTION_OK')
