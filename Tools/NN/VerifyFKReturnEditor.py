"""Read reflection and compile the existing pose BP; do not modify/save assets."""
import json
from pathlib import Path
import unreal
root=Path(unreal.Paths.project_dir()).resolve()
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
assert ed.get_editor_world().get_path_name()=='/Game/testNN.testNN'
checks=[('ProphecyFKReturnLibrary','set_attack_fk_return',['nn_takeover_coefficient','alpha_hold']),
 ('ProphecyFKReturnLibrary','set_attack_fk_return_profile',['return_time','bone_inertia']),
 ('ProphecyAttackEndExtensionLibrary','set_attack_end_extension',[]),
 ('ProphecyUpperCheckpointLibrary','set_upper_checkpoint',[]),
 ('ProphecyUpperBodyInertiaLibrary','set_attack_upper_body_inertia',['arms_alpha']),
 ('ProphecySlashReturnLibrary','set_slash_right_arm_return_to_neutral',['left_hold_duration_seconds','left_blend_to_nn_duration_seconds','left_alpha'])]
signatures={}
for cls,method,params in checks:
    doc=getattr(getattr(unreal,cls),method).__doc__ or ''
    for param in params:assert param in doc,(cls,method,param)
    signatures[cls+'.'+method]=doc.splitlines()[0]
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent');assert bp
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
inspection=(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in inspection and 'native_properties=0 pin_types=0' in inspection,inspection
report={'passed':True,'world':ed.get_editor_world().get_path_name(),'signatures':signatures,'blueprint':inspection,'assets_saved':False}
(root/'Saved/FKReturn/editor-verification.json').write_text(json.dumps(report,indent=2))
print('FK_RETURN_EDITOR_VERIFIED '+json.dumps(report))
