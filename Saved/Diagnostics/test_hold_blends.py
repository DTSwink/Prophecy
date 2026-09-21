import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
for path,method,args in [
 ('/Script/GameAnimationSample3.ProphecyLowerTemperingLibrary','BlendLocomotionLowerBodyTemperingToNormal',(None,1.,0.)),
 ('/Script/GameAnimationSample3.ProphecyAttackRecoveryLibrary','SetAttackToLocomotionBlend',(None,1.,0.))]:
 cls=unreal.load_class(None,path)
 assert cls and unreal.get_default_object(cls).call_method(method,args) is False
print('HOLD_BLEND_SIGNATURES_LOADED')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),
 'Automation RunTests Prophecy.NN.LowerTempering.ReturnTimeline+Prophecy.NN.PolicyBlend.AttackRecovery')
