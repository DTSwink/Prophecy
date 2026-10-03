import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve Play'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RestorePelvisOnlyInertia')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
report=(folder/'RestorePelvisOnlyPins.txt').read_text(encoding='utf-8-sig')
assert 'values_and_links_preserved=1' in report,report
types=(folder/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in types and 'native_properties=0' in types and 'pin_types=0' in types,types
unreal.SystemLibrary.execute_console_command(w,'Automation RunTests Prophecy.NN.PhysicalTargets.RecoveryCalfLength+Prophecy.NN.Presentation')
print('PELVIS_ONLY_BLUEPRINT_RESTORED_TESTS_QUEUED')
