import unreal, pathlib, json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None, 'Preserve user Play'
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/AttackBonesSword20261006'
w=ed.get_editor_world()
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RepairLibraryDefaults')
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.RefreshAttackBonesAgent')
report=(p.parent/'AttackBonesAgentPins.txt').read_text(encoding='utf-8-sig')
assert 'nodes=1 ' in report and 'values_and_links_preserved=1' in report and 'status=3' in report, report
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Sword.AuditCollisionGraph')
(p/'after-graph.txt').write_bytes((p.parent/'SwordThigh/BlueprintGraph.txt').read_bytes())
unreal.SystemLibrary.execute_console_command(w,'Prophecy.Editor.LiveAgentTypes Inspect')
(p/'migration-report.txt').write_text(report,encoding='utf-8')
unreal.log('ATTACK_BONES_MIGRATION '+report)
