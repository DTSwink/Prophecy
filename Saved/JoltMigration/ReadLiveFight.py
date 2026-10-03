import json
from pathlib import Path
from datetime import datetime
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world and unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
scratch = Path.home() / '.codex/tmp/ProphecyJolt' / ('VisualStatus-' + stamp + '.json')
target = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration' / ('VisualStatus-' + stamp + '.json')
unreal.SystemLibrary.execute_console_command(world, 'Prophecy.Jolt.VisualStatus ' + scratch.as_posix())
assert scratch.exists()
result = json.loads(scratch.read_text(encoding='utf-8-sig'))
result['game_paused'] = unreal.GameplayStatics.is_game_paused(world)
result['skeletal_pose'] = []
for agent in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
    if not agent.is_jolt_physical_animation_enabled():
        continue
    mesh = agent.get_pose_reference_mesh()
    result['skeletal_pose'].append({'agent': agent.get_name(),
        'actor_location': str(agent.get_actor_location()),
        'pelvis': str(mesh.get_socket_transform('pelvis', unreal.RelativeTransformSpace.RTS_WORLD)),
        'right_hand': str(mesh.get_socket_transform('hand_r', unreal.RelativeTransformSpace.RTS_WORLD)),
        'target': str(agent.get_locomotion_target())})
target.write_text(json.dumps(result, indent=2), encoding='utf-8')
print('VISUAL_STATUS_REPORT ' + str(target))
print(json.dumps(result, indent=2))
