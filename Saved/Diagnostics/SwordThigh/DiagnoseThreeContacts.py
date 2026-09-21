import builtins,json,pathlib,time,traceback,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'This capture starts from the saved setup; stop Play first.'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordThigh/ThreeContacts'
out.mkdir(parents=True,exist_ok=True)
s={'rows':[],'last':-1,'start':time.monotonic()}
builtins._three_contacts=s
bones=['upperarm_r','lowerarm_r','hand_r','thigh_r','thigh_l']
def v(x):return [x.x,x.y,x.z]
def tf(x):return v(x.translation)+[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (out/'capture.json').write_text(json.dumps(dict(reason=reason,rows=s['rows']),indent=2))
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('THREE_CONTACTS',reason,len(s['rows']))
def capture(_):
    try:
        w=ed.get_game_world()
        if not w:
            if time.monotonic()-s['start']>60:finish('No PIE')
            return
        now=unreal.GameplayStatics.get_time_seconds(w)
        if now==s['last']:
            if time.monotonic()-s['start']>60:finish('Paused')
            return
        s['last']=now
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        td=a.get_editor_property('tick debug')
        if 95<=td<=140:
            mesh=a.get_pose_reference_mesh(); sword=a.get_held_sword(); blade=sword.root_component
            r=dict(tick=td,actor=a.get_name(),jolt=a.is_jolt_physical_animation_enabled(),mode=str(a.get_simulation_mode()),attached_inertia=a.get_sword_attached_inertia_scale(),sword_sim=a.is_sword_simulated(),attack=str(a.get_nn_attack_state()),bones={},pairs={},sword=tf(blade.get_world_transform()),mesh_responses=str(mesh.get_collision_response_to_channels()) if hasattr(mesh,'get_collision_response_to_channels') else str(mesh.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PHYSICS_BODY)),sword_response=str(blade.get_collision_response_to_channel(mesh.get_collision_object_type())))
            for bone in bones:
                state=a.get_physical_body_state(bone)
                r['bones'][bone]=dict(visual=tf(mesh.get_socket_transform(bone)),state=str(state),magnet=str(a.get_body_magnetization_settings(bone)))
                if state:
                    r['bones'][bone].update(physical=tf(state[0]),linear=v(state[1]),angular=v(state[2]),sim=state[3])
            for x,y in [('lowerarm_r','thigh_r'),('lowerarm_r','thigh_l'),('hand_r','thigh_r'),('hand_r','thigh_l')]:
                r['pairs'][x+'_'+y]=str(a.get_jolt_body_pair_self_collision_enabled(x,y))
            r['sword_thigh_distances']={}
            low,high=blade.get_local_bounds(); low=v(low); high=v(high)
            axis=max(range(3),key=lambda i:high[i]-low[i])
            for thigh in ['thigh_l','thigh_r']:
                probes=[]
                for k in range(41):
                    p=[(low[i]+high[i])*0.5 for i in range(3)];p[axis]=low[axis]+(high[axis]-low[axis])*k/40
                    pos=unreal.MathLibrary.transform_location(blade.get_world_transform(),unreal.Vector(*p))
                    distance,closest=mesh.get_closest_point_on_collision(pos,thigh)
                    probes.append(dict(p=v(pos),distance=distance))
                r['sword_thigh_distances'][thigh]=probes
            s['rows'].append(r)
            if td in [110,115,125]:
                r['forearm_thigh_overlap_samples']=[]
                frame=mesh.get_socket_transform('lowerarm_r')
                for ix in range(13):
                    for iy in [-4,-2,0,2,4]:
                        for iz in [-4,-2,0,2,4]:
                            pos=unreal.MathLibrary.transform_location(frame,unreal.Vector(-25+ix*2.5,iy,iz))
                            df,_=mesh.get_closest_point_on_collision(pos,'lowerarm_r')
                            if df<=0:
                                dt,_=mesh.get_closest_point_on_collision(pos,'thigh_r')
                                if dt<=0:r['forearm_thigh_overlap_samples'].append(v(pos))
            if 'meta' not in s:
                s['meta']=True
                asset=mesh.get_editor_property('physics_asset_override') or mesh.get_editor_property('skeletal_mesh_asset').get_editor_property('physics_asset')
                meta={'asset':str(asset),'joint_api':[n for n in dir(unreal.ConstraintInstanceBlueprintLibrary) if n.startswith('get_')],'constraints':[], 'bodies':[]}
                try:
                    for c in asset.get_editor_property('constraint_setup'):
                        ci=str(c.get_editor_property('default_instance'))
                        if any(b in ci for b in bones[:3]):meta['constraints'].append(ci)
                except Exception as e:meta['constraint_error']=str(e)
                try:
                    for b in asset.get_editor_property('skeletal_body_setups'):
                        if str(b.get_editor_property('bone_name')) in bones:
                            meta['bodies'].append(dict(bone=str(b.get_editor_property('bone_name')),geometry=str(b.get_editor_property('agg_geom'))))
                except Exception as e:meta['body_error']=str(e)
                meta['runtime_constraints']=[dict(bones=str(unreal.ConstraintInstanceBlueprintLibrary.get_attached_body_names(c)),linear=str(unreal.ConstraintInstanceBlueprintLibrary.get_linear_limits(c)),angular=str(unreal.ConstraintInstanceBlueprintLibrary.get_angular_limits(c))) for c in mesh.get_constraints(True)]
                meta['drive']={}
                for name in ['WorldMagnetizationLinearStrengthScale','WorldMagnetizationAngularStrengthScale','bWorldMagnetizationEnabled']:
                    try:meta['drive'][name]=str(a.get_editor_property(name))
                    except Exception as e:meta['drive'][name]=str(e)
                meta['joint_stabilization']=[dict(bones=str(unreal.ConstraintInstanceBlueprintLibrary.get_attached_body_names(c)),projection=str(unreal.ConstraintInstanceBlueprintLibrary.get_projection_params(c)),conditioning=str(unreal.ConstraintInstanceBlueprintLibrary.get_mass_conditioning_enabled(c)),parent_dominates=str(unreal.ConstraintInstanceBlueprintLibrary.get_parent_dominates(c))) for c in mesh.get_constraints(True)]
                (out/'metadata.json').write_text(json.dumps(meta,indent=2))
        if td>=141:finish('complete')
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(capture)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
