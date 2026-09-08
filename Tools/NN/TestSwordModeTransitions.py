"""Six directed transitions, all rendered bones; transient PIE, no asset saves."""
import unreal, json, traceback, math, time
from pathlib import Path
state={'phase':-1,'handle':None,'rows':[],'index':0,'wall_start':time.monotonic()}
isolate=globals().get('ISOLATE',False)
free_physics=globals().get('FREE_PHYSICS',False)
sword_mode=globals().get('SWORD_SIMULATED',None)
isolate_others=globals().get('ISOLATE_OTHER_AGENTS',False)
pairs=[('Kinematic','Physical'),('Physical','Kinematic'),('Kinematic','HalfSim'),
       ('HalfSim','Kinematic'),('Physical','HalfSim'),('HalfSim','Physical')]
out=Path(unreal.Paths.project_saved_dir()).resolve()/'Sword'/globals().get('OUTPUT','transitions_baseline.json')
def mode(name):
    unreal.SystemLibrary.execute_console_command(world,'ke '+agent.get_path_name()+' SetSimulationMode '+name)
    if isolate:agent.set_actor_tick_enabled(False)
    if free_physics:
        agent.set_physical_drive_strength_multiplier(0.)
        mesh.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
        for i in range(mesh.get_num_bones()):
            name=mesh.get_bone_name(i)
            if agent.set_physical_body_gravity_enabled(name,False):
                mesh.set_physics_linear_velocity(unreal.Vector(),False,name)
                mesh.set_physics_angular_velocity_in_radians(unreal.Vector(),False,name)
        for c in mesh.get_constraints(False):
            lib=unreal.ConstraintInstanceBlueprintLibrary
            l=unreal.LinearConstraintMotion.LCM_FREE;a=unreal.AngularConstraintMotion.ACM_FREE
            lib.set_linear_limits(c,l,l,l,0.)
            lib.set_angular_limits(c,a,180.,a,180.,a,180.)
        sword=agent.call_method('GetHeldSword')
        if sword:
            b=sword.get_component_by_class(unreal.StaticMeshComponent)
            b.set_enable_gravity(False)
            b.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
def bones():
    return [mesh.get_socket_transform(mesh.get_bone_name(i)) for i in range(mesh.get_num_bones())]

def sword_transform():
    s=agent.call_method('GetHeldSword')
    return s.get_component_by_class(unreal.StaticMeshComponent).get_world_transform() if s else None
def detail():
    result={}
    def xyz(p):return [p.x,p.y,p.z]
    def pack(t):return {'p':xyz(t.translation),'q':xyz(t.rotation)+[t.rotation.w],'s':xyz(t.scale3d)}
    for n in ['root','thigh_r','calf_r','calf_twist_01_r','foot_r','hand_r']:
        t=mesh.get_socket_transform(n);parent=mesh.get_parent_bone(n)
        local=unreal.MathLibrary.make_relative_transform(t,mesh.get_socket_transform(parent)) if str(parent)!='None' else t
        row={'render':pack(t),'local':pack(local)}
        body=agent.get_physical_body_state(n)
        if body:row['body']=pack(body[0]);row['linear']=xyz(body[1]);row['angular']=xyz(body[2]);row['body_simulating']=body[3]
        result[n]=row
    return result
def compare(before,after):
    pos=[(a.translation-b.translation).length() for a,b in zip(before,after)]
    angle=[math.degrees(a.rotation.angular_distance(b.rotation)) for a,b in zip(before,after)]
    scale=[(a.scale3d-b.scale3d).length() for a,b in zip(before,after)]
    return {'position_cm':max(pos),'rotation_deg':max(angle),'scale':max(scale),
            'worst_position_bone':str(mesh.get_bone_name(pos.index(max(pos)))),
            'worst_rotation_bone':str(mesh.get_bone_name(angle.index(max(angle))))}
def finish(error=None):
    if state['handle'] is not None: unreal.unregister_slate_post_tick_callback(state['handle']);state['handle']=None
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'passed':error is None,'error':error,'isolate_legacy_bp_follower':isolate,'free_physics_unit_test':free_physics,'sword_simulated':sword_mode,'rows':state['rows']},indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    global world,agent,mesh
    try:
        if time.monotonic()-state['wall_start']>90:raise RuntimeError('Transition test watchdog')
        if state['phase']==-1:
            world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if not world:return
            agents=[a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            if not agents:return
            agent=agents[0];mesh=agent.get_pose_reference_mesh();agent.stop_nn_attack()
            if isolate:
                for other in agents:other.set_actor_tick_enabled(False)
            if isolate_others:
                for other in agents:
                    if other!=agent:other.set_actor_enable_collision(False);other.set_actor_tick_enabled(False)
            if free_physics:agent.set_nn_inference_enabled(False)
            mode(pairs[0][0])
            if sword_mode is not None:
                agent.set_fist_closed_levels(1.,1.,0.)
                assert agent.call_method('EquipSword',args=(sword_mode,))
                mode(pairs[0][0])
            state.update(phase=0,start=unreal.GameplayStatics.get_time_seconds(world));return
        now=unreal.GameplayStatics.get_time_seconds(world)
        if isolate:agent.apply_nn_pose_kinematically(0.)
        if state['phase']==0 and now-state['start']>.5:
            before=bones();details=detail();sword_before=sword_transform();src,dst=pairs[state['index']];mode(dst);after=bones()
            state['rows'].append({'from':src,'to':dst,'bones':len(before),'immediate':compare(before,after),'frames':[],
                                  'before_details':details,'after_details':detail()})
            immediate=state['rows'][-1]['immediate']
            assert immediate['position_cm']<.001 and immediate['rotation_deg']<.01 and immediate['scale']<.00001,immediate
            if sword_before:
                sword_after=sword_transform()
                delta={'cm':(sword_after.translation-sword_before.translation).length(),'deg':math.degrees(sword_after.rotation.angular_distance(sword_before.rotation))}
                state['rows'][-1]['sword_immediate']=delta
                assert delta['cm']<.001 and delta['deg']<.01,delta
            state.update(phase=1,previous=after,start=now)
        elif state['phase']==1:
            current=bones()
            if not state['rows'][-1]['frames']:state['rows'][-1]['first_frame_details']=detail()
            state['rows'][-1]['frames'].append({'dt':dt,'elapsed':now-state['start'],**compare(state['previous'],current)})
            state['previous']=current
            if now-state['start']>.5:
                state['index']+=1
                if state['index']==len(pairs):finish();return
                mode(pairs[state['index']][0]);state.update(phase=0,start=now)
    except Exception:finish(traceback.format_exc())
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
state['handle']=unreal.register_slate_post_tick_callback(tick)
print('Six-mode transition baseline scheduled')
