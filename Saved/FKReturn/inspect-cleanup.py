from pathlib import Path
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None, 'Preserve user Play'
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/FKReturn/upper-cleanup'
out.mkdir(exist_ok=True)
(out/'graph-before.txt').write_bytes((root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes())
print('BLUEPRINT_API', [n for n in dir(unreal.BlueprintEditorLibrary) if any(s in n for s in ['node','graph','export','refresh'])])
print('DIRTY_CONTENT', [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
print('DIRTY_MAPS', [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
print('GRAPH_DUMP', str(out/'graph-before.txt'))
