import unreal
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not sub.get_game_world(), 'Stop PIE before upgrading component templates.'
world=sub.get_editor_world()
for path,component in (('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent','PhysicalMesh'),('/Game/_mygame/sword/A_Sword','sword')):
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.PhysicsReceiver.Upgrade '+path+' '+component)
print('Receiver upgrades requested; inspect PhysicsReceiver upgrade results before continuing.')
