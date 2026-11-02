"""Owned offscreen oil-only scene: controlled bottle motion, settling, inversion and recording.
No saved fixture changes. Compiles/saves only BP_OilBottle's new native component.
"""
import json,math,shutil,struct,subprocess,time,traceback,zlib
from pathlib import Path
import unreal as u
assert '-ProphecyOilLiquidCheck' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Liquid';out.mkdir(parents=True,exist_ok=True)
bp=u.load_asset('/Game/_mygame/OilBottle/BP_OilBottle')
u.BlueprintEditorLibrary.compile_blueprint(bp)
assert u.EditorAssetLibrary.save_loaded_asset(bp,False)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
for a in actors.get_all_level_actors():
    if isinstance(a,u.ProphecyOilBottle):actors.destroy_actor(a)
base=u.Vector(-980,-380,70)
a=actors.spawn_actor_from_class(bp.generated_class(),base);a.set_actor_label('LiquidReview');a.tags=['LiquidReview']
a.set_editor_property('launch_on_play',False);a.set_editor_property('break_on_hit',False)
a.bottle.set_simulate_physics(False);a.bottle.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
s={'tick':0,'world':None,'last':-1,'start':time.monotonic(),'rows':[],'costs':[],'captures':[],'encoders':[], 'last_updates':-1,'checks':{}}
u.EditorPythonScripting.set_keep_python_script_alive(True)
def spawn(w,cls,pos,target):
    tr=u.Transform(location=pos,rotation=u.MathLibrary.find_look_at_rotation(pos,target));gs=u.get_default_object(u.GameplayStatics)
    a=gs.call_method('BeginDeferredActorSpawnFromClass',(w,cls,tr,u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    return gs.call_method('FinishSpawningActor',(a,tr,u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
def payload(path):
    data=path.read_bytes();offset=8
    while offset+12<=len(data):
        size=struct.unpack_from('>I',data,offset)[0];end=offset+size+12
        assert end<=len(data) and zlib.crc32(data[offset+4:end-4])==struct.unpack_from('>I',data,end-4)[0]
        kind=data[offset+4:offset+8];offset=end
        if kind==b'IEND':return data[:offset]
    raise ValueError('Invalid PNG')
def init(w):
    s['bottle']=u.GameplayStatics.get_all_actors_with_tag(w,'LiquidReview')[0]
    s['liquid']=s['bottle'].get_component_by_class(u.ProphecyOilLiquid)
    c=s['liquid'];assert c and c.is_visible()
    s['checks']['same_splash_material']=c.get_material(0)==s['bottle'].oil.droplet_material
    s['checks']['no_collision']=c.get_collision_enabled()==u.CollisionEnabled.NO_COLLISION
    # Small local review lights, only in this unsaved fixture, so clear glass/oil
    # can be judged against the floor instead of the lab's unlit sky.
    light=spawn(w,u.RectLight,base+u.Vector(15,-50,75),base+u.Vector(0,0,12))
    lc=light.light_component;lc.set_mobility(u.ComponentMobility.MOVABLE)
    lc.set_editor_property('intensity',1600.);lc.set_editor_property('source_width',45.)
    lc.set_editor_property('source_height',80.);lc.set_editor_property('attenuation_radius',300.)
    lc.set_editor_property('cast_shadows',False)
    for name,offset in [('side',(36,-70,65)),('above',(30,-45,82))]:
        target=base+u.Vector(0,0,12);a=spawn(w,u.SceneCapture2D,base+u.Vector(*offset),target)
        c=a.get_component_by_class(u.SceneCaptureComponent2D)
        c.capture_every_frame=False;c.capture_on_movement=False;c.always_persist_rendering_state=True
        c.capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR;c.fov_angle=42
        c.texture_target=u.RenderingLibrary.create_render_target2d(w,640,640,u.TextureRenderTargetFormat.RTF_RGBA8)
        log=(out/(name+'-encode.log')).open('wb')
        p=subprocess.Popen([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','png','-framerate','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','19','-threads','1','-pix_fmt','yuv420p',str(out/(name+'.mp4'))],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        s['captures'].append((name,c));s['encoders'].append((p,log))
    for cmd in ['r.MotionBlurQuality 0','r.ScreenPercentage 100','t.MaxFPS 0']:u.SystemLibrary.execute_console_command(w,cmd)
def finish(reason):
    u.unregister_slate_post_tick_callback(s['callback'])
    exits=[]
    for p,log in s['encoders']:
        p.stdin.close();exits.append(p.wait(timeout=30));log.close()
    if s['world']==ed.get_game_world():level.editor_request_end_play()
    checks=s['checks'];checks['completed']=reason=='complete';checks['encoded']=exits==[0,0]
    checks['volume_preserved']=bool(s['rows']) and max(r['error'] for r in s['rows'])<.0005
    costs=sorted(s['costs'])
    (out/'test.json').write_text(json.dumps({'reason':reason,'checks':checks,'rows':s['rows'],'update_us':{'samples':len(costs),'median':costs[len(costs)//2] if costs else 0,'p95':costs[int(len(costs)*.95)] if costs else 0,'max':max(costs,default=0)},'source':'Actual Unreal captures. Bottle motion scripted to reveal visual response; no fluid physics or extra contacts.'},indent=2))
    print('OIL_LIQUID_FINISHED',checks)
    u.EditorPythonScripting.set_keep_python_script_alive(False)
def tick(_):
    try:
        if time.monotonic()-s['start']>480:return finish('timeout')
        w=ed.get_game_world()
        if not w:return
        now=u.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now;s['world']=w;s['tick']+=1;n=s['tick']
        if n==1:init(w)
        a=s['bottle'];c=s['liquid']
        if 60<n<=240:
            phase=(n-60)*2*math.pi/180
            a.set_actor_location_and_rotation(base+u.Vector(5*math.sin(phase*2),0,0),u.Rotator(28*math.sin(phase),0,16*math.sin(phase*2)),False,True)
        if n==240:a.set_actor_location_and_rotation(base,u.Rotator(),False,True)
        if 480<n<=540:
            t=(n-480)/60;angle=180*(t*t*(3-2*t));a.set_actor_rotation(u.Rotator(angle,0,0),True)
        if n==470:s['checks']['settled_tick_off']=not c.is_component_tick_enabled()
        if n==500:s['checks']['movement_woke']=c.is_component_tick_enabled()
        if n==900:s['checks']['inverted_settled_tick_off']=not c.is_component_tick_enabled()
        updates=c.mesh_updates
        if updates!=s['last_updates']:s['costs'].append(c.last_update_microseconds);s['last_updates']=updates
        if n%15==0:s['rows'].append({'tick':n,'normal':[c.surface_normal.x,c.surface_normal.y,c.surface_normal.z],'error':c.volume_error,'updates':updates,'ticking':c.is_component_tick_enabled()})
        if n<=720 and n%2==0:
            for (name,cap),(p,_) in zip(s['captures'],s['encoders']):
                cap.capture_scene();u.RenderingLibrary.export_render_target(w,cap.texture_target,str(out),name+'-buffer.png')
                data=payload(out/(name+'-buffer.png'));p.stdin.write(data)
                if n in (60,150,300,470,660):(out/(name+f'-{n}.png')).write_bytes(data)
        if n==930:
            c.fill_amount=0;c.refresh_liquid();s['checks']['empty_no_work']=not c.is_visible() and not c.is_component_tick_enabled()
        if n>=940:return finish('complete')
    except Exception:return finish(traceback.format_exc())
s['callback']=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
