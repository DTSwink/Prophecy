import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for path in ('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent','/Game/_mygame/sword/A_Sword'):
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.SystemLibrary.execute_console_command(world,'Prophecy.PhysicsReceiver.Inspect '+path)
print('Receiver template inspection requested; no asset changes.')
