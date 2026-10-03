import unreal
for path in ['/Script/GameAnimationSample3.ProphecySpecialRecoveryEvents','/Script/GameAnimationSample3.ProphecySpecialRecoveryEvents:OnNNUpperSpecialEnded','/Script/GameAnimationSample3.ProphecySpecialRecoveryEvents:OnNNLowerSpecialEnded','/Script/GameAnimationSample3.ProphecySpecialRecoveryEvents:OnNNSpecialEnded']:
    print('REGION_REFLECTION',path,unreal.find_object(None,path))
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.SplitSpecialRecovery')
