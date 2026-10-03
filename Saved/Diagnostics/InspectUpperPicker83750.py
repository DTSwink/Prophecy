import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('UPPER83750_USER_PLAY',bool(ed.get_game_world()))
enum=unreal.find_object(None,'/Script/GameAnimationSample3.EProphecyUpperCheckpoint')
assert enum
print('ENUM',enum)
helper=unreal.get_default_object(unreal.load_class(None,'/Script/Engine.KismetNodeHelperLibrary'))
entries=[(i,helper.call_method('GetEnumeratorName',(enum,i)),helper.call_method('GetEnumeratorUserFriendlyName',(enum,i))) for i in range(5)]
print('LIVE_ENUM_CHOICES',entries)
assert str(entries[4][1]).endswith('HandVelocityBound83750') and entries[4][2]=='October 1 - Hand Velocity Bound (83750)',entries
for name in ['SetUpperCheckpoint','GetUpperCheckpoint']:
    assert unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyUpperCheckpointLibrary:'+name)
print('UPPER_PICKER_FUNCTIONS_PRESENT')
if not ed.get_game_world():
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
