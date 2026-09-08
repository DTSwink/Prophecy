"""Observe existing kinematic attacks in PIE. No input, mode, FPS or asset changes."""
import json
import time
import traceback
from pathlib import Path
import unreal

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_game_world() or unreal.EditorLevelLibrary.get_game_world()
assert world, 'PIE must be running'
calf_audit = {'handle': None, 'until': time.monotonic() + 6.0, 'rows': []}


def finish_calf_audit(error=None):
    if calf_audit['handle'] is not None:
        unreal.unregister_slate_post_tick_callback(calf_audit['handle'])
        calf_audit['handle'] = None
    rows = calf_audit['rows']
    maximum = max((abs(v-1.0) for row in rows for v in row['scale']), default=None)
    path = Path(unreal.Paths.project_saved_dir()).resolve() / 'SlashParity/attack_calf_scale.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'passed': error is None and maximum is not None and maximum < 1e-5,
        'error': error, 'max_scale_error': maximum, 'samples': len(rows), 'rows': rows}, indent=2))
    print('Calf scale audit:', len(rows), 'samples, maximum scale error=', maximum, 'error=', error)


def sample_calf_scale(_dt):
    try:
        if time.monotonic() >= calf_audit['until']:
            finish_calf_audit(); return
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.ProphecyAgent):
            attack = actor.call_method('GetNNAttackState')
            if not attack or attack[-1] < 3 or actor.get_simulation_mode() != unreal.ProphecyAgentSimulationMode.KINEMATIC:
                continue
            mesh = actor.get_pose_reference_mesh()
            for bone in ['calf_l', 'calf_r']:
                scale = mesh.get_socket_transform(bone, unreal.RelativeTransformSpace.RTS_COMPONENT).scale3d
                calf_audit['rows'].append({'actor': actor.get_name(), 'attack': str(attack[0]),
                    'frame': attack[-1], 'half': attack[1], 'bone': bone, 'scale': [scale.x, scale.y, scale.z]})
    except Exception:
        finish_calf_audit(traceback.format_exc())


calf_audit['handle'] = unreal.register_slate_post_tick_callback(sample_calf_scale)
print('Observing calf scale for six seconds without controlling the agents')
