import builtins,json,pathlib,time,traceback,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
force_block=bool(getattr(builtins,'_sword_thigh_force_block',False))
out=pathlib.Path(unreal.Paths.project_saved_dir())/('Diagnostics/SwordThigh/ForceBlock' if force_block else 'Diagnostics/SwordThigh')
out.mkdir(parents=True,exist_ok=True)
s=dict(rows=[],last=-1,start=time.monotonic())
builtins._sword_thigh_capture=s
def v(x):return [x.x,x.y,x.z]
def tf(x):return v(x.translation)+[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]
def done(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (out/'capture.json').write_text(json.dumps(dict(reason=reason,rows=s['rows'])))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('SWORD_THIGH_CAPTURE',reason,len(s['rows']))
def tick(_):
    try:
        w=ed.get_game_world()
        if not w:
            if time.monotonic()-s['start']>60:done('No PIE world')
            return
        now=unreal.GameplayStatics.get_time_seconds(w)
        if now==s['last']:
            if time.monotonic()-s['start']>60:done('World paused')
            return
        s['last']=now
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent):
            if a != unreal.GameplayStatics.get_player_pawn(w,0):continue
            sword=a.get_held_sword()
            if not sword:continue
            blade=sword.root_component
            mesh=a.get_pose_reference_mesh()
            td=a.get_editor_property('tick debug')
            if force_block and td==6:
                blade.set_collision_response_to_channel(unreal.CollisionChannel.ECC_PHYSICS_BODY,unreal.CollisionResponseType.ECR_BLOCK)
            r=dict(t=now,tick=td,actor=a.get_name(),handle=a.get_agent_handle().index,mode=str(a.get_simulation_mode()),jolt=a.is_jolt_physical_animation_enabled(),sword_simulated=a.is_sword_simulated(),inertia=a.get_sword_inertia_scale(),attack=str(a.get_nn_attack_state()),blade_class=blade.get_class().get_name(),collision=str(blade.get_collision_enabled()),chaos_sim=blade.is_simulating_physics(),parent=str(blade.get_attach_parent()),socket=str(blade.get_attach_socket_name()),profile=str(blade.get_collision_profile_name()),object_type=str(blade.get_collision_object_type()),physics_response=str(blade.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PHYSICS_BODY)),sword=tf(blade.get_world_transform()),hand=tf(mesh.get_socket_transform('hand_r')),thigh=tf(mesh.get_socket_transform('thigh_r')),calf=tf(mesh.get_socket_transform('calf_r')))
            if 75<=td<=115:
                r['thigh_physics']=str(a.get_physical_body_state('thigh_r'))
                r['mesh_object_type']=str(mesh.get_collision_object_type())
                r['mesh_physics_response']=str(mesh.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PHYSICS_BODY))
                r['sword_to_mesh_response']=str(blade.get_collision_response_to_channel(mesh.get_collision_object_type()))
                hand=mesh.get_socket_transform('hand_r')
                r['relative_to_hand']=tf(unreal.MathLibrary.make_relative_transform(blade.get_world_transform(),hand))
                r['authored_grip']=tf(a.get_editor_property('sword_grip_transform'))
                r['primitive_components']=[dict(name=c.get_name(),cls=c.get_class().get_name(),collision=str(c.get_collision_enabled()),sim=c.is_simulating_physics()) for c in sword.get_components_by_class(unreal.PrimitiveComponent)]
                if td in (80,97,110):
                    native_path=pathlib.Path(unreal.Paths.project_saved_dir()).resolve()/'Diagnostics/SwordThigh'/('native_%s_%s.json'%(int(s['start']*1000),td))
                    # Console command argument parsing needs a path without spaces.
                    native_path=pathlib.Path('C:/Users/singerie/AppData/Local/Temp')/native_path.name
                    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.VisualStatus '+native_path.as_posix())
                    r['native_report']=str(native_path)
                lo,hi=blade.get_local_bounds()
                low,high=v(lo),v(hi)
                axis=max(range(3),key=lambda i:high[i]-low[i])
                r['local_bounds']=[low,high]
                probes=[]
                for k in range(25):
                    p=[(low[i]+high[i])/2 for i in range(3)]
                    p[axis]=low[axis]+(high[axis]-low[axis])*k/24
                    pos=unreal.MathLibrary.transform_location(blade.get_world_transform(),unreal.Vector(*p))
                    distance,point=mesh.get_closest_point_on_collision(pos,'thigh_r')
                    probes.append(dict(p=v(pos),distance=distance,closest=v(point)))
                r['thigh_probes']=probes
            s['rows'].append(r)
        if now>=4:done('complete')
    except Exception:done(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
