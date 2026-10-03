import json
from pathlib import Path
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/FKReturn/feedback-fix'
assert json.loads((out/'graph-verification.json').read_text())['passed']
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(),'Preserve unsaved maps'
dirty=[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
assert all(p=='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent' for p in dirty),dirty
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
(out/'saved-pin.json').write_text(json.dumps({'saved':bp.get_path_name(),'alpha_hold_default':0}))
unreal.SystemLibrary.quit_editor()
