import pathlib, unreal, json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None
root=pathlib.Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/Diagnostics/RemoveRunPinBoost20261003'
audit=root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'
def command(value): unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),value)
command('Prophecy.Sword.AuditCollisionGraph')
(out/'before-graph.txt').write_bytes(audit.read_bytes())
command('Prophecy.Editor.RemoveRunPinBoosts')
assert (out/'cleanup-result.txt').exists(), 'Cleanup did not run; inspect preflight'
report=(out/'cleanup-result.txt').read_text(encoding='utf-8-sig')
assert 'removed=5 connections_ok=1 status=3' in report,report
command('Prophecy.Sword.AuditCollisionGraph')
(out/'after-graph.txt').write_bytes(audit.read_bytes())
print(report)
print('DIRTY',json.dumps({'content':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()], 'maps':[p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}))
