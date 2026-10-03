"""Exercise the actual A_Sword Blueprint, fixed grip, physics toggle, drop and despawn."""
import unreal, json, traceback, math, time
from pathlib import Path
state={'phase':-1,'handle':None,'rows':[],'index':0,'wall_start':time.monotonic()}
no_contacts=globals().get('NO_CONTACTS',False)
keep_tick=globals().get('KEEP_AGENT_TICK',False)
isolate_others=globals().get('ISOLATE_OTHER_AGENTS',False)
drop_attached=globals().get('DROP_FROM_ATTACHED',False)
out=Path(unreal.Paths.project_saved_dir()).resolve()/'Sword'/globals().get('OUTPUT','hold_audit.json')
def mode(n):
    unreal.SystemLibrary.execute_console_command(world,'ke '+agent.get_path_name()+' SetSimulationMode '+n)
    # Isolate the sword/transition code from the user's old Blueprint velocity follower.
    if not keep_tick:agent.set_actor_tick_enabled(False)
    if no_contacts:
        agent.set_physical_drive_strength_multiplier(0.)
        mesh.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
        for i in range(mesh.get_num_bones()):agent.set_physical_body_gravity_enabled(mesh.get_bone_name(i),False)
def clock():return unreal.GameplayStatics.get_time_seconds(world)
def call(name,*args):
    result=agent.call_method(name,args=args)
    if no_contacts and name in ['EquipSword','SetSwordSimulated'] and result:
        b=blade();b.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE);b.set_enable_gravity(False)
    return result
def blade():return call('GetHeldSword').get_component_by_class(unreal.StaticMeshComponent)
def report(label):
    b=blade(); actual=b.get_world_transform()
    data=json.loads((Path(unreal.Paths.project_saved_dir()).resolve()/'SlashChain/sword_preview.json').read_text())['sword']
    grip=unreal.Transform(location=unreal.Vector(*data['location_cm']),rotation=unreal.Quat(*data['quaternion_xyzw']).rotator(),scale=unreal.Vector(*data['scale']))
    hand=mesh.get_socket_transform('hand_r')
    target=unreal.MathLibrary.compose_transforms(grip,hand)
    row={'label':label,'physics':b.is_simulating_physics(),
         'holder':agent.get_path_name(),
         'position_cm':(actual.translation-target.translation).length(),
         'rotation_deg':math.degrees(actual.rotation.angular_distance(target.rotation)),
         'mass_kg':b.get_mass(),'actor_class':call('GetHeldSword').get_class().get_path_name(),
         'hand':str(hand.translation),'blade':str(actual.translation)}
    row['cut_count']=len(call('GetHeldSword').get_editor_property('cuts'))
    row['sword_constraint_count']=len(call('GetHeldSword').get_components_by_class(unreal.PhysicsConstraintComponent))
    row['cuts']=str(call('GetHeldSword').get_editor_property('cuts'))
    row['constraints']=[str(c.get_constrained_components()) for c in call('GetHeldSword').get_components_by_class(unreal.PhysicsConstraintComponent)]
    body=agent.get_physical_body_state('hand_r')
    if body:
        bw=body[0]
        row['render_hand_vs_body_cm']=(hand.translation-bw.translation).length()
        row['render_hand_vs_body_deg']=math.degrees(hand.rotation.angular_distance(bw.rotation))
    state['rows'].append(row)
    return row
def finish(error=None):
    if state['handle'] is not None: unreal.unregister_slate_post_tick_callback(state['handle']);state['handle']=None
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'passed':error is None,'error':error,'no_contacts_diagnostic':no_contacts,
                              'original_agent_bp_tick_enabled':keep_tick,'other_agents_collision_disabled':isolate_others,
                              'drop_from_attached':drop_attached,'rows':state['rows']},indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(dt):
    global world,agent,mesh,dropped
    try:
        # Wall-clock watchdog also catches a Blueprint pausing game time.
        if time.monotonic()-state['wall_start']>45:raise RuntimeError('Sword test timed out (check existing Blueprint pause logic)')
        if state['phase']==-1:
            world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if not world:return
            aa=[a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent) if a.has_valid_agent_handle()]
            if not aa:return
            agent=aa[0];mesh=agent.get_pose_reference_mesh();agent.stop_nn_attack()
            if isolate_others:
                for other in aa:
                    if other!=agent:
                        other.set_actor_enable_collision(False)
                        other.set_actor_tick_enabled(False)
            mode('Kinematic');agent.set_fist_closed_levels(1,1,0)
            state.update(phase=0,start=clock());return
        t=clock()-state['start']
        if t<.6:return
        p=state['phase']
        if p==0:
            assert call('EquipSword',False),'Equip attached failed'
            row=report('kinematic attached immediate');assert row['position_cm']<.01,row
        elif p==1:
            row=report('kinematic attached held');assert row['position_cm']<.01,row
            assert call('SetSwordSimulated',True),'Physics toggle failed'
            report('kinematic constraint immediate')
        elif p==2:
            row=report('kinematic constraint settled');assert row['position_cm']<.25 and row['rotation_deg']<1,row
            mode('HalfSim');report('half sim constraint immediate')
        elif p==3:
            row=report('half sim constraint settled');assert row['position_cm']<.25 and row['rotation_deg']<2,row
            assert call('SetSwordSimulated',False)
            row=report('half sim attached');assert row['position_cm']<.01,row
            mode('Physical')
        elif p==4:
            row=report('sim attached');assert row['position_cm']<.01,row
            if not drop_attached:assert call('SetSwordSimulated',True)
        elif p==5:
            row=report('sim attached before drop' if drop_attached else 'sim constrained')
            # A failed hold must not be labelled a passing sword test.
            assert row['position_cm']<.25 and row['rotation_deg']<2,row
            before=blade().get_world_transform()
            v=blade().get_physics_linear_velocity();w=blade().get_physics_angular_velocity_in_radians()
            dropped=call('DropSword')
            assert dropped and call('GetHeldSword') is None
            b=dropped.get_component_by_class(unreal.StaticMeshComponent)
            assert b.is_simulating_physics()
            assert (before.translation-b.get_world_location()).length()<.001
            if not drop_attached:
                assert (b.get_physics_linear_velocity()-v).length()<.001
                assert (b.get_physics_angular_velocity_in_radians()-w).length()<.001
            state['rows'].append({'label':'drop initial momentum','linear_cm_s':str(b.get_physics_linear_velocity()),'angular_rad_s':str(b.get_physics_angular_velocity_in_radians())})
            state['drop_start']=b.get_world_location()
        elif p==6:
            b=dropped.get_component_by_class(unreal.StaticMeshComponent)
            state['rows'].append({'label':'dropped movement','cm':(b.get_world_location()-state['drop_start']).length()})
            assert call('EquipSword',False)
            new=call('GetHeldSword');call('HideSword')
            assert call('GetHeldSword') is None and dropped.is_actor_being_destroyed()==False
            state['rows'].append({'label':'hide clears held sword, dropped sword survives'})
            finish();return
        state['phase']+=1;state['start']=clock()
    except Exception:finish(traceback.format_exc())
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
state['handle']=unreal.register_slate_post_tick_callback(tick)
print('Sword hold audit scheduled')
