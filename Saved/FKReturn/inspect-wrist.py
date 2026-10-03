from pathlib import Path
import unreal
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/FKReturn/wrist-investigation';out.mkdir(exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
(out/'current-graph.txt').write_bytes((root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes())
print('PLAY',bool(ed.get_game_world()))
