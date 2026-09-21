import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
cdo=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyRootPhysicsLibrary'))
for fn in ('SetRootMagicVelocity2','SetRootMagicAngVelocity2'):
 assert cdo.call_method(fn,(None,unreal.Vector(),False)) is False
 print(fn,'loaded')
for fn in ('GetRootMagicVelocity2','GetRootMagicAngVelocity2'):
 assert cdo.call_method(fn,(None,)).length()==0
 print(fn,'loaded')
print('PIE preserved:',bool(ed.get_game_world()))
