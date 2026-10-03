import unreal
dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()) + list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
if dirty:
    raise RuntimeError('Refusing shutdown: unsaved packages ' + str([x.get_path_name() for x in dirty]))
unreal.SystemLibrary.quit_editor()
