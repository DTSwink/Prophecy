"""Owns Play only in a separately launched -ProphecyOilCheck editor."""
import json,time,traceback
from pathlib import Path
import unreal as u
assert '-ProphecyOilCheck' in u.SystemLibrary.get_command_line()
u.EditorPythonScripting.set_keep_python_script_alive(True)
editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not editor.get_game_world()
assert 'M_OilTest' in editor.get_editor_world().get_path_name()
if '-ProphecyOilFinalize' in u.SystemLibrary.get_command_line():
    # Only the dedicated map's authored demo is tuned; gameplay maps are never opened.
    actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        if actor.get_actor_label()=='Oil_Bottle_Mesh':actor.set_actor_location(u.Vector(-1100,-400,180),False,True)
    u.EditorLevelLibrary.set_level_viewport_camera_info(u.Vector(-1400,-1150,800),u.MathLibrary.find_look_at_rotation(u.Vector(-1400,-1150,800),u.Vector(-750,-300,10)))
    level.save_current_level()
out=Path(u.Paths.project_saved_dir())/'Diagnostics/Oil';out.mkdir(parents=True,exist_ok=True)
state={'start':time.monotonic(),'ticks':0,'rows':[],'world':None,'extras':[],'task':None,'last_game_time':-1,'shot_path':None,'direct_planar':False,'tint_tracking':True,'tint_seen':False}
def camera(w,pos,target):
    tr=u.Transform(location=u.Vector(*pos),rotation=u.MathLibrary.find_look_at_rotation(u.Vector(*pos),u.Vector(*target)))
    gs=u.get_default_object(u.GameplayStatics)
    a=gs.call_method('BeginDeferredActorSpawnFromClass',(w,u.CameraActor,tr,u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    a=gs.call_method('FinishSpawningActor',(a,tr,u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    a.get_component_by_class(u.CameraComponent).set_field_of_view(65)
    return a
def finish(reason):
    u.unregister_slate_post_tick_callback(state['callback'])
    if state['world'] and editor.get_game_world()==state['world']:
        u.GameplayStatics.set_game_paused(state['world'],False);level.editor_request_end_play()
    rows=state['rows'];last=rows[-1] if rows else {}
    checks={'completed':reason=='complete','bottles_broke':bool(rows) and last.get('bottles')==0,
        'oil_started':any(r.get('patches',0)>0 for r in rows),
        'oil_faded':any(any(0<a<.9 for a in r.get('amounts',[])) for r in rows),
        'cleanup':bool(rows) and last.get('patches')==0 and not last.get('amounts'),
        'landscape':any(r.get('landscape_bodies',0)>0 and r.get('terrain_matches',0)>50 and r.get('terrain_holes',0)>0 and r.get('terrain_mismatches',1)==0 for r in rows),
        'limbs':any(len(r.get('limbs',[]))==4 for r in rows),
        'direct_planar_one_patch':state['direct_planar'],
        'moving_surface':any(r.get('tick',0)>180 and r.get('moving_surface_coverage',0)>.9 for r in rows),
        'optional_splash_cleaned':bool(rows) and last.get('splash_components')==0,
        'healthy':bool(rows) and not any(r.get('faulted',True) for r in rows),
        'tint_tracks_coating':state['tint_seen'] and state['tint_tracking']}
    (out/'scene.json').write_text(json.dumps({'reason':reason,'checks':checks,'rows':rows},indent=2))
    print('OIL_SCENE_FINISHED',reason)
    u.EditorPythonScripting.set_keep_python_script_alive(False)
def tick(_):
    try:
        if time.monotonic()-state['start']>240:return finish('timeout')
        w=editor.get_game_world()
        if not w:return
        if state['shot_path']:
            # Wait for the actual image write, not just the queued screenshot task.
            if state['shot_path'].exists() and state['shot_path'].stat().st_mtime>=state['shot_time']:
                state['task']=None;state['shot_path']=None;u.GameplayStatics.set_game_paused(w,False)
            return
        game_time=u.GameplayStatics.get_time_seconds(w)
        if game_time==state['last_game_time']:return
        state['last_game_time']=game_time
        state['world']=w;state['ticks']+=1;n=state['ticks']
        if n==2:
            state['mesh_camera']=camera(w,(-1400,-1150,800),(-750,-300,10))
            state['terrain_camera']=camera(w,(2200,-1300,1100),(1050,-150,0))
            pc=u.GameplayStatics.get_player_controller(w,0)
            if pc:pc.set_view_target_with_blend(state['mesh_camera'])
        if n in (178,208,898,1698):
            pc=u.GameplayStatics.get_player_controller(w,0)
            if pc:pc.set_view_target_with_blend(state['terrain_camera' if n==208 else 'mesh_camera'])
        if n==120:
            settings=u.ProphecyOilSettings(radius=80,slipperiness=1,hold_duration=3,fade_duration=5,
                decal_material=u.load_asset('/Game/_mygame/Tests/Oil/M_OilPlaceholder'),
                tint_material=u.load_asset('/Game/_mygame/Tests/Oil/M_OilTint'))
            for loc in [(-300,500,130),(-600,600,120),(-650,-400,0)]:
                u.SystemLibrary.execute_console_command(w,'Prophecy.Oil.Probe')
                before=json.loads((out/'probe.json').read_text(encoding='utf-8-sig'))['patches']
                spill=u.ProphecyOilLibrary.spawn_oil_spill(w,u.Vector(*loc),u.Vector(0,0,1),settings)
                state['extras'].append(bool(spill))
                if loc==(-300,500,130) and spill:
                    u.SystemLibrary.execute_console_command(w,'Prophecy.Oil.Probe')
                    state['direct_planar']=json.loads((out/'probe.json').read_text(encoding='utf-8-sig'))['patches']==before+1
        if n%60==0:
            spills=u.GameplayStatics.get_all_actors_of_class(w,u.ProphecyOilSpill)
            for owner in [w.get_world_settings()]:
                decals=owner.get_components_by_class(u.DecalComponent)
                coat=[d for d in decals if d.get_decal_material().get_base_material().get_name()=='M_OilPlaceholder']
                tint=[d for d in decals if d.get_decal_material().get_base_material().get_name()=='M_OilTint']
                state['tint_seen']|=bool(tint)
                state['tint_tracking']&=len(coat)==len(tint) and all(any(
                    all(abs(a-b)<.001 for a,b in zip(d.get_world_location().to_tuple(),t.get_world_location().to_tuple())) and
                    all(abs(a-b)<.001 for a,b in zip(d.get_world_rotation().to_tuple(),t.get_world_rotation().to_tuple())) and
                    d.get_editor_property('decal_size').to_tuple()==t.get_editor_property('decal_size').to_tuple() for t in tint) for d in coat)
            bottles=u.GameplayStatics.get_all_actors_of_class(w,u.ProphecyOilBottle)
            u.SystemLibrary.execute_console_command(w,'Prophecy.Oil.Probe'+(' Push' if n==120 else (' Move' if n==180 else '')))
            row=json.loads((out/'probe.json').read_text(encoding='utf-8-sig'))
            effects=[c for c in w.get_world_settings().get_components_by_class(u.NiagaraComponent) if c.get_asset() and c.get_asset().get_name()=='NS_OilSplashPlaceholder']
            row.update({'tick':n,'bottles':len(bottles),'amounts':[s.get_oil_amount() for s in spills],'splash_components':len(effects)})
            if n==60:
                row['placement']=[{'radius':s.settings.radius,'decals':[{'pos':c.get_world_location().to_tuple(),'rot':c.get_world_rotation().to_tuple(),'size':c.get_editor_property('decal_size').to_tuple()} for c in s.get_components_by_class(u.DecalComponent)]} for s in spills]
            state['rows'].append(row)
            print('OIL_SCENE_TICK',n,row['patches'],row['failure'])
        if n in (180,210,900,1700) and '-nullrhi' not in u.SystemLibrary.get_command_line().lower():
            shot={180:'mesh-wet',210:'landscape-wet',900:'mesh-fading',1700:'mesh-dry'}[n]
            u.GameplayStatics.set_game_paused(w,True)
            cam=state['terrain_camera' if n==210 else 'mesh_camera']
            pc=u.GameplayStatics.get_player_controller(w,0)
            if pc:pc.set_view_target_with_blend(cam)
            state['shot_path']=out/(shot+'.png');state['shot_time']=time.time()
            state['task']=u.AutomationLibrary.take_high_res_screenshot(1280,900,str(state['shot_path']),camera=cam,delay=0)
        if n>=1800:return finish('complete')
    except Exception:return finish(traceback.format_exc())
state['callback']=u.register_slate_post_tick_callback(tick)
u.SystemLibrary.execute_console_command(editor.get_editor_world(),'t.MaxFPS 0')
level.editor_request_begin_play()
