"""Close Unreal for the explicitly approved final build, only after saved-work checks."""
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages(), 'Unsaved map appeared; editor remains open'
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(), 'Unsaved content appeared; editor remains open'
print('APPROVED_EDITOR_CLOSE_FOR_FINAL_PACKAGE')
unreal.SystemLibrary.quit_editor()
