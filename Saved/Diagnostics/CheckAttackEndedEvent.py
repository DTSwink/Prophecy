import unreal

event = unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyAgent:OnNNAttackEnded')
assert event, 'Attack-ended event missing from the loaded base class'
bp = unreal.load_object(None, '/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
assert bp, 'Pose-agent Blueprint missing'
cls = bp.generated_class()
assert cls, 'Pose-agent generated class missing'
assert isinstance(unreal.get_default_object(cls), unreal.ProphecyAgent), 'Pose-agent does not inherit the event base'
print('Attack-ended event reflected on base agent; pose-agent Blueprint inherits that base. No scene or assets changed.')
