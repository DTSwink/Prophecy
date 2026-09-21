import builtins,json,pathlib,time,traceback,unreal,sys
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Stop Play first'
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordThigh/Isolation'
root.mkdir(parents=True,exist_ok=True)
cases=json.loads(sys.argv[1])
s=dict(index=-1,rows=[],last=-1,started=time.monotonic(),phase='next',applied=False)
builtins._contact_isolation=s
def v(x):return [x.x,x.y,x.z]
def tf(x):return v(x.translation)+[x.rotation.x,x.rotation.y,x.rotation.z,x.rotation.w]
def cmd(w,c):
    a=unreal.GameplayStatics.get_player_pawn(w,0)
    p=a.get_physical_body_state('hand_r')[0].translation
    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment '+c+' at %.9f %.9f %.9f'%(p.x,p.y,p.z))
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    (root/'status.json').write_text(json.dumps(dict(reason=reason,index=s['index'],case=s.get('case'))))
    if ed.get_game_world():unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print('CONTACT_ISOLATION',reason)
def tick(_):
    try:
        w=ed.get_game_world()
        if s['phase']=='next':
            if w:return
            s['index']+=1
            if s['index']>=len(cases):finish('complete');return
            s.update(case=cases[s['index']],rows=[],last=-1,started=time.monotonic(),phase='play',applied=False)
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
            return
        if time.monotonic()-s['started']>90:finish('timeout');return
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        td=a.get_editor_property('tick debug')
        if td==s['last']:return
        s['last']=td
        label=s['case']['name']
        if td>=10 and not s['applied']:
            assert a.is_jolt_physical_animation_enabled(), 'Possessed pawn is not Jolt physical'
            for c in s['case'].get('commands',[]):cmd(w,c)
            if 'inertia' in s['case']:a.set_sword_attached_inertia_scale(s['case']['inertia'])
            if 'magnet' in s['case']:
                lin,ang=s['case']['magnet']
                for b in ['upperarm_r','lowerarm_r','hand_r']:a.set_body_magnetization(b,True,lin,ang)
            if 'ccd_node' in s['case']:
                mode=getattr(unreal.ProphecyJoltCCDMode,s['case']['ccd_node'])
                result=a.set_jolt_ccd_mode(mode)
                assert a.get_jolt_ccd_mode()==mode, str(result)
            if 'iterations_node' in s['case']:
                v_it,p_it=s['case']['iterations_node']
                result=a.set_jolt_solver_iterations(v_it,p_it)
                assert tuple(a.get_jolt_solver_iterations())==(v_it,p_it),str(result)
            s['applied']=True
            print('CONTACT_CASE',label,td)
            sword=a.get_held_sword()
            print('CONTACT_METADATA',label, 'socket', a.get_editor_property('SwordHandSocket'), 'sword', sword, 'components', sword.get_components_by_class(unreal.ActorComponent) if sword else None)
            if sword:
                print('CONTACT_SWORD',label,'root',sword.root_component,'mesh',[(m.get_name(),str(m.get_world_transform()),str(m.get_editor_property('body_instance'))) for m in sword.get_components_by_class(unreal.StaticMeshComponent)])
        if 60<=td<=s['case'].get('end',160):
            cmd(w,'capture '+label+'_'+str(td))
            row=dict(tick=td,actor=a.get_name(),mode=str(a.get_simulation_mode()),inertia=a.get_sword_attached_inertia_scale(),sword_sim=a.is_sword_simulated(),bones={})
            mesh=a.get_pose_reference_mesh()
            for b in ['upperarm_r','lowerarm_r','hand_r','thigh_r','thigh_l']:
                t,vel,ang,sim=a.get_physical_body_state(b)
                row['bones'][b]=dict(physical=tf(t),linear=v(vel),angular=v(ang),visual=tf(mesh.get_socket_transform(b)))
            s['rows'].append(row)
        if td>=s['case'].get('end',160)+1:
            (root/(label+'.json')).write_text(json.dumps(dict(case=s['case'],rows=s['rows']),indent=2))
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
            s['phase']='next'
    except Exception:finish(traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
