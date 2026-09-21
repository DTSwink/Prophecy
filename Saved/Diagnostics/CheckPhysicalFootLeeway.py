import unreal

function=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyPhysicalFootTargetLibrary:SetPhysicalFootTargetClampLeeway')
assert function, 'Physical foot target clamp leeway node not reflected'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=editor.get_editor_world()
print('Physical foot target clamp leeway node reflected. PIE:',bool(editor.get_game_world()))
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Physics.FootTargetLeeway')
