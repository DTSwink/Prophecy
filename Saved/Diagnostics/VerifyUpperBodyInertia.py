import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
lib=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary')
assert lib,'Missing inertia library'
print('UPPER_BODY_INERTIA_LIBRARY',lib)
if not ed.get_game_world():
    unreal.BlueprintEditorLibrary.compile_blueprint(unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'))
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
tests=['Prophecy.NN.UpperBodyInertia','Prophecy.NN.CoreTempering','Prophecy.NN.HandRecovery','Prophecy.NN.LowerTempering','Prophecy.NN.PolicyBlend','Prophecy.NN.SlashReturn','Prophecy.Blends.SixtyTickClock','Prophecy.Agent.PhysicalBlends','Prophecy.Agent.PhysicalContext','Prophecy.PhysicalProfiles.ClampSnapshots','Prophecy.Joints.DampingProfileBlend','Prophecy.Joints.AngularLimitBlend','Prophecy.Joints.KickFootLeeway','Prophecy.Camera.AttackOffsetFade','Prophecy.Root.KickSelfBalancingException']
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests '+'+'.join(tests))
print('UPPER_INERTIA_AND_RETIREMENT_CHECKS_QUEUED')
