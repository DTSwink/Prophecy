import pathlib
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'Preserve user Play'
world = editor.get_editor_world()
saved = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics'

def report(name, require_compiled=True):
    data = (saved / name).read_bytes()
    value = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    print(name, value)
    if require_compiled:
        assert 'status=3' in value or 'status=5' in value, value
    return value

unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Editor.RepairLibraryDefaults')
assert 'other_values_and_wiring_preserved=1' in report('LiveLibraryDefaults.txt', False)
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Editor.RefreshUpperInertiaSpace')
controls = report('UpperInertiaControlsPins.txt')
assert 'preserved=1' in controls and 'defaults=1' in controls, controls
assert 'nodes=0' not in controls, controls
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world, 'Automation RunTests Prophecy.NN.UpperBodyInertia')
print('UPPER_CORE_ARMS_BLUEPRINT_REFRESHED_AND_FOCUSED_TESTS_REQUESTED')
