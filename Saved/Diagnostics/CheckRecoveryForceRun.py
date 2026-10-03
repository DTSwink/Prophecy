import unreal,pathlib
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RefreshRecoveryPinOrder')
report=(folder/'RecoveryPinOrder.txt').read_text(encoding='utf-8-sig')
assert 'values_and_links_preserved=1' in report and 'status=3 ' in report,report
print('FORCE_RUN_REFRESH',report)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RepairLibraryDefaults')
report=(folder/'LiveLibraryDefaults.txt').read_text(encoding='utf-8-sig')
assert 'status=3 ' in report and 'other_values_and_wiring_preserved=1' in report,report
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
raw=(folder/'SwordThigh/BlueprintGraph.txt').read_bytes()
graph=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig').replace('\r\n','\n')
nodes=[x for x in graph.split('\n\n') if '| Set Attack To Locomotion Blend\n' in x]
assert nodes and all('bForceRun=false None ->\n' in x+'\n' for x in nodes),nodes
print('FORCE_RUN_VERIFIED',len(nodes),'existing nodes, unchecked default, complete Blueprint compile')
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.NN.PolicyBlend.AttackRecovery+Prophecy.Blends.SixtyTickClock')
