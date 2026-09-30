"""Owned current-setup rollout: fixed NN wrists and measured simulated attachment.

Run with Saved/RunUnrealRemote.py; optional argument Physical previews literal
simulation-mode pins, then restores them after PIE. Never saves an asset.
"""
import builtins, json, math, pathlib, sys, time, traceback, unreal

ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Preserve user Play'
physical=len(sys.argv)>1 and sys.argv[1]=='Physical'
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FixedArms20260930'
folder.mkdir(parents=True,exist_ok=True)
contract=json.loads((pathlib.Path(unreal.Paths.project_content_dir())/'locomotion/NN/prophecy_upper_body_runtime.json').read_text())
lengths=[a[1]*100 for a in contract['arm_limb_lengths_m']]
state=dict(rows=[],last=None,frames=0,wall=time.monotonic(),ending=False)
builtins._fixed_arm_check=state
if physical:unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.PreviewFixedArmMode Physical')

def vec(p):return [p.x,p.y,p.z]
def transform(t):return dict(p=vec(t.translation),q=[t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w])

def finish(reason):
    state['ending']=True
    report=dict(reason=reason,preview_physical=physical,rest_lengths_cm=lengths,rows=state['rows'])
    (folder/('physical.json' if physical else 'current.json')).write_text(json.dumps(report,separators=(',',':')))
    level.editor_request_end_play()
    print('FIXED_ARMS_CAPTURE_DONE',reason,len(state['rows']))

def tick(_):
    try:
        world=ed.get_game_world()
        if state['ending']:
            if world:return
            if physical:unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.PreviewFixedArmMode restore')
            unreal.unregister_slate_post_tick_callback(state['cb'])
            print('FIXED_ARMS_CLEANUP_COMPLETE')
            return
        if time.monotonic()-state['wall']>180:finish('Timeout');return
        if not world:return
        now=unreal.GameplayStatics.get_time_seconds(world)
        if now==state['last']:return
        state['last']=now;state['frames']+=1
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent):
            if not actor.is_player_controlled():continue
            pose=actor.read_nn_future_world_pose()
            if not pose:continue
            names,future,presented,alpha=pose
            index={str(n):i for i,n in enumerate(names)}
            if any(b not in index for b in ['lowerarm_l','hand_l','lowerarm_r','hand_r']):continue
            row=dict(t=now,tick=int(actor.get_editor_property('tick debug')),attack=str(actor.get_nn_attack_state()),mode=str(actor.get_simulation_mode()),alpha=alpha,nn={},meshes={})
            for label,transforms in [('future',future),('presented',presented)]:
                bones={b:transform(transforms[index[b]]) for b in ['lowerarm_l','hand_l','lowerarm_r','hand_r']}
                errors=[abs(math.dist(bones['lowerarm_'+side]['p'],bones['hand_'+side]['p'])-lengths[i]) for i,side in enumerate(['l','r'])]
                assert max(errors)<0.001,(row['tick'],label,errors)
                assert all(math.isfinite(v) for b in bones.values() for values in b.values() for v in values)
                row['nn'][label]=dict(bones=bones,errors_cm=errors)
            for mesh in actor.get_components_by_class(unreal.SkeletalMeshComponent):
                bones={b:transform(mesh.get_socket_transform(b,unreal.RelativeTransformSpace.RTS_WORLD)) for b in ['lowerarm_l','hand_l','lowerarm_r','hand_r'] if mesh.get_bone_index(b)>=0}
                if len(bones)!=4:continue
                row['meshes'][mesh.get_name()]=dict(bones=bones,lengths_cm=[math.dist(bones['lowerarm_'+side]['p'],bones['hand_'+side]['p']) for side in ['l','r']])
                if actor.get_simulation_mode()==unreal.ProphecyAgentSimulationMode.KINEMATIC:
                    assert max(abs(v-lengths[i]) for i,v in enumerate(row['meshes'][mesh.get_name()]['lengths_cm']))<0.001,(row['tick'],mesh.get_name(),'rendered wrist detached')
            state['rows'].append(row)
        if state['frames']>=620:finish('Complete')
    except Exception:finish(traceback.format_exc())

state['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('FIXED_ARMS_CAPTURE_STARTED', 'Physical' if physical else 'current')
