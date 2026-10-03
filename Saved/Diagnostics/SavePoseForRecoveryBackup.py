import unreal, shutil, time
from pathlib import Path
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
root=Path(unreal.Paths.project_dir())
source=root/'Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset'
shutil.copy2(source,root/'Saved/Diagnostics'/('PoseBeforeRecoveryBackup-'+time.strftime('%Y%m%d-%H%M%S')+'.uasset'))
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
report=(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'native_properties=0 pin_types=0 status=3' in report, report
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
print('POSE_BLUEPRINT_COMPILED_AND_SAVED',source.stat().st_size)
