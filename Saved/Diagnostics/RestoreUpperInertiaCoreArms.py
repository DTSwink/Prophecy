import pathlib
import unreal

editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'Preserve user Play'
world=editor.get_editor_world()
saved=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RefreshUpperInertiaSpace')
data=(saved/'UpperInertiaControlsPins.txt').read_bytes()
report=data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
print('RESTORED_SPLIT_INERTIA',report)
assert ('status=3' in report or 'status=5' in report) and 'preserved=1' in report and 'defaults=1' in report
assert 'nodes=0' not in report
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
print('SPLIT_CORE_ARMS_READY_NO_ASSET_SAVE')
