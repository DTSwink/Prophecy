"""Read authored and live per-body drive settings without changing the scene."""
import json
from datetime import datetime
from pathlib import Path
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
report = []
for world in [editor.get_editor_world(), editor.get_game_world()]:
    if not world:
        continue
    for agent in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
        row = {'world': world.get_path_name(), 'name': agent.get_name(), 'label': agent.get_actor_label(),
               'jolt': agent.is_jolt_physical_animation_enabled(), 'mode': str(agent.get_simulation_mode()),
               'location': str(agent.get_actor_location()), 'sword': str(agent.get_held_sword()),
               'settings': {}, 'bodies': {}, 'meshes': []}
        for key in ['world_magnetization_enabled', 'world_magnetization_linear_strength_scale',
                    'world_magnetization_angular_strength_scale', 'auto_apply_world_magnetization']:
            row['settings'][key] = str(agent.get_editor_property(key))
        for bone in ['pelvis', 'spine_01', 'spine_02', 'spine_03', 'neck_01', 'head',
                     'upperarm_r', 'lowerarm_r', 'hand_r', 'thigh_r', 'calf_r', 'foot_r']:
            row['bodies'][bone] = str(agent.get_body_magnetization_settings(bone))
        for mesh in agent.get_components_by_class(unreal.SkeletalMeshComponent):
            row['meshes'].append({'name': mesh.get_name(), 'visible': mesh.is_visible(),
                                  'asset': str(mesh.get_editor_property('skeletal_mesh_asset'))})
        report.append(row)
target = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration' / ('VisualMagnetization-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
target.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('MAGNETIZATION_REPORT', str(target))
print(json.dumps(report, indent=2))
