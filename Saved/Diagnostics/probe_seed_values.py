import unreal
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent');c=unreal.get_default_object(bp.generated_class())
r=unreal.RandomStream(initial_seed=100);print('BEFORE',r.export_text());r.reset();print('AFTER',r.export_text())
print('CDO',c.get_editor_property('Random Stream debug').export_text())
