"""Live-mesh fist validation against the visible source animation's deformation.

Run before PIE with closed_fist open. Starts/ends PIE; never saves assets.
Unlike the original track-copy test, compares transformed skin-space probe
points in a common reference wrist frame across the two different bone bases.
"""
import json
import math
import traceback
from pathlib import Path
import unreal

clip=unreal.load_asset('/Game/_mygame/closed_fist')
preview=next(o for o in unreal.ObjectIterator(unreal.DebugSkelMeshComponent)
             if 'AnimationEditorPreviewActor' in o.get_path_name() and o.get_anim_instance()
             and o.get_anim_instance().get_animation_asset()==clip)
source_mod=unreal.SkeletonModifier(); source_mod.set_skeletal_mesh(preview.get_skeletal_mesh_asset())
names=[str(n) for n in source_mod.get_all_bone_names() if str(n).startswith(('index_','middle_','ring_','pinky_','thumb_'))]
source_ref={n:source_mod.get_bone_transform(n,True) for n in names+['hand_l','hand_r']}
source_pose={n:preview.get_socket_transform(n,unreal.RelativeTransformSpace.RTS_COMPONENT) for n in names+['hand_l','hand_r']}
state={'handle':None,'phase':-1,'mode':0,'start':0.,'checks':[]}
modes=['Physical','Kinematic','HalfSim']
output=Path(unreal.Paths.project_saved_dir()).resolve()/'AttackFists/deformation_audit.json'
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()

def now(): return unreal.GameplayStatics.get_time_seconds(world)
def xyz(p): return [p.x,p.y,p.z]

def check(closed):
    # The engine's post-physics component transforms are the actual rendered bones.
    actual={n:mesh.get_socket_transform(n,unreal.RelativeTransformSpace.RTS_COMPONENT) for n in names+['hand_l','hand_r']}
    maximum=0.; worst=''
    for n in names:
        h='hand_'+n[-1]
        for offset in [unreal.Vector(0,0,0),unreal.Vector(1,0,0),unreal.Vector(0,1,0),unreal.Vector(0,0,1)]:
            point=target_ref[n].translation+offset
            got=actual[n].transform_location(target_ref[n].inverse_transform_location(point))
            got=target_ref[h].transform_location(actual[h].inverse_transform_location(got))
            expected=point
            if closed:
                expected=source_pose[n].transform_location(source_ref[n].inverse_transform_location(point))
                expected=source_ref[h].transform_location(source_pose[h].inverse_transform_location(expected))
            error=(got-expected).length()
            if error>maximum: maximum=error; worst=n
    row={'mode':modes[state['mode']],'closed':closed,'max_skin_probe_cm':maximum,'worst':worst,'levels':list(agent.get_fist_closed_levels())}
    state['checks'].append(row)
    assert maximum<.005,row

def finish(error=None):
    if state['handle'] is not None:
        unreal.unregister_slate_post_tick_callback(state['handle']); state['handle']=None
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'passed':error is None,'error':error,'checks':state['checks']},indent=2))
    unreal.log('Fist deformation audit '+str(output)+' error='+str(error))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()

def tick(dt):
    global world,agent,mesh,target_ref
    try:
        if state['phase']==-1:
            world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if not world: return
            agents=[a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            if not agents:return
            agent=agents[0]; mesh=agent.get_pose_reference_mesh()
            agent.set_actor_tick_enabled(False)
            agent.stop_nn_attack()
            target_mod=unreal.SkeletonModifier(); target_mod.set_skeletal_mesh(mesh.get_skeletal_mesh_asset())
            target_ref={n:target_mod.get_bone_transform(n,True) for n in names+['hand_l','hand_r']}
            unreal.SystemLibrary.execute_console_command(world,'ke '+agent.get_path_name()+' SetSimulationMode Physical')
            agent.set_actor_tick_enabled(False)
            assert agent.set_fist_closed_levels(0,0,0)
            state['phase']=0;state['start']=now();return
        elapsed=now()-state['start']
        agent.apply_nn_pose_kinematically(0.)
        if state['phase']==0 and elapsed>.3:
            check(False)
            assert agent.set_fist_closed_levels(1,1,.4)
            state['phase']=1;state['start']=now()
        elif state['phase']==1 and elapsed>.8:
            check(True)
            state['phase']=2;state['start']=now()
        elif state['phase']==2 and elapsed>.6:
            check(True)  # Persistent, not a one-frame pose.
            assert agent.set_fist_closed_levels(.25,.75,.2)
            state['phase']=3;state['start']=now()
        elif state['phase']==3 and elapsed>.5:
            assert math.dist(agent.get_fist_closed_levels(),[.25,.75])<1e-6
            assert agent.set_fist_closed_levels(0,0,.3)
            state['phase']=4;state['start']=now()
        elif state['phase']==4 and elapsed>.6:
            check(False)
            state['mode']+=1
            if state['mode']==len(modes): finish();return
            unreal.SystemLibrary.execute_console_command(world,'ke '+agent.get_path_name()+' SetSimulationMode '+modes[state['mode']])
            # Isolate user BP hand commands; evaluate the normal kinematic path above.
            agent.set_actor_tick_enabled(False)
            assert agent.set_fist_closed_levels(0,0,0)
            state['phase']=0;state['start']=now()
    except Exception: finish(traceback.format_exc())

state['handle']=unreal.register_slate_post_tick_callback(tick)
print('Fist deformation test scheduled')
