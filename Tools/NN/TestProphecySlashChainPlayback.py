"""PIE-only: compare rendered bones to the reference and observe two loop seams."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world
actor=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.SkeletalMeshActor) if a.get_actor_label()=='SlashChain30_Reference_Looping')
component=actor.get_component_by_class(unreal.SkeletalMeshComponent)
sequence=unreal.load_asset('/Game/_mygame/Tests/SlashChain30/AS_SlashChain30_Reference')
data=json.loads((root/'Saved/SlashChain/animation_tracks.json').read_text())
options=unreal.AnimPoseEvaluationOptions()
options.set_editor_property('optional_skeletal_mesh',component.get_skinned_asset())
options.set_editor_property('should_retarget',True)
camera=actor.call_method('AddComponentByClass',args=(unreal.CameraComponent.static_class(),False,unreal.Transform(),False))
# Bound the entire recorded motion, so no attack can leave the diagnostic view.
points=[p for frame in data['world_positions_cm'] for p in frame]
low=[min(p[i] for p in points) for i in range(3)]; high=[max(p[i] for p in points) for i in range(3)]
center=actor.get_actor_location()+unreal.Vector(*[(a+b)/2 for a,b in zip(low,high)])
extent=max(b-a for a,b in zip(low,high))
location=center+unreal.Vector(-extent*1.1,extent*1.45,extent*.35)
camera.set_world_location_and_rotation(location,unreal.MathLibrary.find_look_at_rotation(location,center),False,True)
pc=unreal.GameplayStatics.get_player_controller(world,0)
previous_view=pc.get_view_target()
pc.set_view_target_with_blend(actor,0)
state={'handle':None,'start':time.monotonic(),'last':component.get_position(),'loops':0,'samples':0,'max_mm':0.,'worst':None,'shots':[]}

def finish(error=None):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    state['handle']=None
    pc.set_view_target_with_blend(previous_view,0)
    camera.destroy_component(actor)
    report={k:v for k,v in state.items() if k not in ['handle','start','last']}
    report.update(error=error,passed=not error and state['loops']>=2 and state['max_mm']<1.)
    (root/'Saved/SlashChain/playback_audit.json').write_text(json.dumps(report,indent=2))

def tick(delta):
    try:
        current=component.get_position()
        if current < state['last']-.1: state['loops']+=1
        state['last']=current
        pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(sequence,current,options)
        for bone in data['bone_names']:
            local=unreal.AnimPoseExtensions.get_bone_pose(pose,bone,unreal.AnimPoseSpaces.WORLD)
            expected=component.get_world_transform().transform_location(local.translation)
            actual=component.get_socket_location(bone)
            error=(expected-actual).length()*10
            if error>state['max_mm']: state['max_mm']=error; state['worst']={'bone':bone,'time':current,'mm':error}
        state['samples']+=1
        if state['samples'] in (15,120):
            path=root/f"Saved/SlashChain/reference_live_{len(state['shots'])+1}.png"
            unreal.SystemLibrary.execute_console_command(world,f'HighResShot filename="{path.as_posix()}" 1280x720')
            state['shots'].append(str(path))
        if state['loops']>=2: finish()
        elif time.monotonic()-state['start']>75: finish('Timed out before two complete loops')
    except Exception: finish(traceback.format_exc())

state['handle']=unreal.register_slate_post_tick_callback(tick)
print('Checking looping reference for two seams; no user actor changes.')
