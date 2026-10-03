import json
from pathlib import Path
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/FKReturn/upper-cleanup'
assert json.loads((out/'graph-verification.json').read_text())['passed']
assert json.loads((out/'scene-check.json').read_text())['unchanged']
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
inspection=(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in inspection and 'native_properties=0 pin_types=0' in inspection,inspection
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(out/'graph-after.txt').write_bytes((root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes())
receipt={'saved':bp.get_path_name(),'blueprint_inspection':inspection,'play':bool(ed.get_game_world()),
 'remaining_dirty_content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
 'remaining_dirty_maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(out/'save-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
