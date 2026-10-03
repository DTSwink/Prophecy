import json
from pathlib import Path
import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None, 'Preserve user Play'
root=Path(unreal.Paths.project_dir()).resolve()
out=root/'Saved/FKReturn/upper-cleanup'
world=ed.get_editor_world()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
def scene():
    return {a.get_path_name(): str(a.get_actor_transform()) for a in actors.get_all_level_actors()}
def graph(name):
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Sword.AuditCollisionGraph')
    (out/name).write_bytes((root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt').read_bytes())
before=scene()
graph('graph-before.txt')
unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.RemoveRetiredUpperRecovery')
report=(out/'cleanup-result.txt').read_text(encoding='utf-8-sig')
assert 'connections_ok=1 status=3' in report, report
graph('graph-after.txt')
after=scene()
(out/'scene-check.json').write_text(json.dumps({'unchanged':before==after,'before':before,'after':after},indent=2))
assert before==after, 'Scene changed during BP cleanup'
print(report)
print('SCENE_UNCHANGED', len(before))
print('PLAY', bool(ed.get_game_world()))
