"""Real Unreal/Jolt recording in a dedicated process; no asset saves or desktop capture.
Streams two reused PNG buffers into ffmpeg, rather than retaining frame sequences.
"""
import json, math, shutil, struct, subprocess, time, traceback, zlib
from pathlib import Path
import unreal as u

assert '-ProphecyOilVideo' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not ed.get_game_world()
assert 'M_OilTest' in ed.get_editor_world().get_path_name()
angles='-ProphecyOilAngles' in u.SystemLibrary.get_command_line()
airborne=angles or '-ProphecyOilAirborne' in u.SystemLibrary.get_command_line()
fps=60 if angles else 30
landing=airborne or '-ProphecyOilLanding' in u.SystemLibrary.get_command_line()
union=landing or '-ProphecyOilUnion' in u.SystemLibrary.get_command_line()
full_splash=union or '-ProphecyOilSplash' in u.SystemLibrary.get_command_line()
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil'/('Airborne/Angles' if angles else ('Airborne/Video' if airborne else ('Landing/Video' if landing else ('Union/Video' if union else ('Splash/Video' if full_splash else ('Edge/Video' if '-ProphecyOilEdge' in u.SystemLibrary.get_command_line() else 'Revision/Video'))))))
if '-ProphecyOilNiagaraFlower' in u.SystemLibrary.get_command_line():out=out.parents[1]/'NiagaraFlower/Angles'
if '-ProphecyOilBottleVideo' in u.SystemLibrary.get_command_line():out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Video'
out.mkdir(parents=True,exist_ok=True)
if '-ProphecyOilNiagaraFlower' in u.SystemLibrary.get_command_line():
    (out/'loaded-assets.json').write_text(json.dumps([
        {'bottle':a.get_actor_label(),'spray':str(a.get_editor_property('oil').splash_system)}
        for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors() if isinstance(a,u.ProphecyOilBottle)],indent=2))
ffmpeg=shutil.which('ffmpeg');assert ffmpeg
u.EditorPythonScripting.set_keep_python_script_alive(True)
s={'world':None,'tick':0,'last_time':-1,'start':time.monotonic(),'encoders':[],
   'captures':[],'frames':0,'rows':[],'flight_before_stains':False,'landing_ticks':[],
   'previous_decals':0,'faded':False,'views':{},'sheet_seen':False,'sheet_cleaned':False,
   'sheet_at_landing':False,'physics':[],'previous_patches':0,'last_sheet_tick':0}

def spawn(w,cls,pos,look):
    tr=u.Transform(location=u.Vector(*pos),rotation=u.MathLibrary.find_look_at_rotation(u.Vector(*pos),u.Vector(*look)))
    gs=u.get_default_object(u.GameplayStatics)
    a=gs.call_method('BeginDeferredActorSpawnFromClass',(w,cls,tr,u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
    return gs.call_method('FinishSpawningActor',(a,tr,u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))

def init(w):
    views=[('mesh',(-1160,-670,220),(-960,-380,25)),('landscape',(410,-520,230),(710,-210,10))] if full_splash else [('mesh',(-1300,-780,310),(-960,-380,25)),('landscape',(270,-610,340),(710,-210,10))]
    if landing:views.append(('dry',(-1160,-170,220),(-960,120,25)))
    if angles:views=[('angled',(-1160,-670,220),(-960,-380,25)),('overhead',(-990,-400,420),(-990,-400,0)),('low',(-990,-690,22),(-990,-400,18))]
    for name,pos,target in views:
        a=spawn(w,u.SceneCapture2D,pos,target)
        c=a.get_component_by_class(u.SceneCaptureComponent2D)
        c.capture_every_frame=False;c.capture_on_movement=False
        c.set_editor_property('always_persist_rendering_state',True)
        c.capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR;c.fov_angle=65
        c.texture_target=u.RenderingLibrary.create_render_target2d(w,1280,720,u.TextureRenderTargetFormat.RTF_RGBA8)
        log=(out/(name+'-encode.log')).open('wb')
        args=[ffmpeg,'-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','png','-framerate',str(fps),'-i','pipe:0',
              '-an','-c:v','libx264','-preset','fast','-crf','19','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(out/(name+'.mp4'))]
        p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        s['encoders'].append((p,log));s['captures'].append((name,c))
        s['views'][name]=(pos,target)
    # Render-only settings in this isolated process. Gameplay settings/assets remain unchanged.
    for cmd in ['r.ScreenPercentage 100','r.MotionBlurQuality 0','t.MaxFPS 0']:
        u.SystemLibrary.execute_console_command(w,cmd)

def png_payload(path):
    # UE's reused file writer can leave bytes after IEND when a new PNG is shorter.
    # Decode exactly one validated PNG, never feed that stale tail to image2pipe.
    data=path.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n'
    offset=8
    while offset+12<=len(data):
        size=struct.unpack_from('>I',data,offset)[0];end=offset+size+12
        assert end<=len(data)
        assert zlib.crc32(data[offset+4:end-4])==struct.unpack_from('>I',data,end-4)[0]
        kind=data[offset+4:offset+8];offset=end
        if kind==b'IEND':return data[:offset]
    raise ValueError('Incomplete PNG export')

def finish(reason):
    u.unregister_slate_post_tick_callback(s['callback'])
    results=[]
    for p,log in s['encoders']:
        try:p.stdin.close();results.append(p.wait(timeout=30))
        except Exception:p.terminate();results.append(-1)
        log.close()
    if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
    checks={'flight_before_stains':s['flight_before_stains'],
        'multiple_landing_ticks':len(s['landing_ticks'])>2,'fade_seen':s['faded'],
        'cleanup':bool(s['rows']) and s['rows'][-1]['spills']==0}
    if landing:
        checks['sheet_reaches_landing']=s['sheet_at_landing']
        checks['wet_cube_slides_further']=False
        if s['physics']:
            first,last=s['physics'][0],s['physics'][-1]
            if all(k in first and k in last for k in ['wet','dry']):
                wet=abs(last['wet']['x']-first['wet']['x']);dry=abs(last['dry']['x']-first['dry']['x'])
                checks['wet_cube_slides_further']=wet>dry*2+15
                s['travel_cm']={'wet':wet,'dry':dry}
    (out/'recording.json').write_text(json.dumps({'reason':reason,'frames':s['frames'],'fps':fps,'ticks':s['tick'],
        'encoder_exits':results,'rows':s['rows'],'checks':checks,
        'landing_ticks':s['landing_ticks'],'sheet_seen':s['sheet_seen'],'sheet_cleaned':s['sheet_cleaned'],
        'last_sheet_tick':s['last_sheet_tick'],'physics':s['physics'],'travel_cm':s.get('travel_cm'),
        'source':'Actual Unreal SceneCapture2D / native Jolt; '+('every unpaused tick through180' if angles else 'one output frame per two unpaused game ticks')+'; no artificial oil patches; no asset saves.',
        'physics_demo':'Both existing sliders receive the same one-time -150cm/s X velocity at tick180; then native physics only.' if landing else None},indent=2))
    print('OIL_VIDEO_FINISHED',reason,s['frames'],results)
    u.EditorPythonScripting.set_keep_python_script_alive(False)

def tick(_):
    try:
        if time.monotonic()-s['start']>600:return finish('timeout')
        w=ed.get_game_world()
        if not w:return
        now=u.GameplayStatics.get_time_seconds(w)
        if now==s['last_time']:return
        s['last_time']=now;s['world']=w;s['tick']+=1;n=s['tick']
        if n==1:init(w)
        spills=u.GameplayStatics.get_all_actors_of_class(w,u.ProphecyOilSpill)
        decals=len(w.get_world_settings().get_components_by_class(u.DecalComponent))
        flying=sum(len(x.get_components_by_class(u.InstancedStaticMeshComponent))+len(x.get_components_by_class(u.NiagaraComponent)) for x in spills)
        sheets=sum(len(x.get_components_by_class(u.ProceduralMeshComponent)) for x in spills)
        s['sheet_seen']|=sheets>0
        s['sheet_at_landing']|=sheets>0 and decals>0
        if sheets:s['last_sheet_tick']=n
        s['sheet_cleaned']|=s['sheet_seen'] and n>=120 and sheets==0
        if flying and not decals:s['flight_before_stains']=True
        if not landing and decals>s['previous_decals']:s['landing_ticks'].append(n)
        s['previous_decals']=decals
        if landing and (n<=120 or 180<=n<=330) and n%6==0:
            u.SystemLibrary.execute_console_command(w,'Prophecy.Oil.Probe'+(' SlideDemo' if n==180 else ''))
            audit=json.loads((out.parents[1]/'probe.json').read_text(encoding='utf-8-sig'))
            if audit['patches']>s['previous_patches']:s['landing_ticks'].append(n)
            s['previous_patches']=audit['patches']
            if n>=180:s['physics'].append({'tick':n,**{r['slider']:r for r in audit['objects'] if 'slider' in r}})
        if (angles and n<=180) or (not angles and n%2==0):
            for (name,c),(p,_) in zip(s['captures'],s['encoders']):
                if n==10 and name=='mesh' and '-ProphecyOilBottleVideo' in u.SystemLibrary.get_command_line():
                    bottles=u.GameplayStatics.get_all_actors_of_class(w,u.ProphecyOilBottle)
                    bottle=next((b for b in bottles if b.get_actor_location().x<0),None)
                    if bottle:
                        focus,extent,radius=u.SystemLibrary.get_component_bounds(bottle.get_editor_property('bottle'))
                        (out/'bottle-pose.json').write_text(json.dumps({'location':str(bottle.get_actor_location()),'bounds':str(focus),'extent':str(extent)}))
                        eye=focus+u.Vector(50,-80,110)
                        c.get_owner().set_actor_location_and_rotation(eye,u.MathLibrary.find_look_at_rotation(eye,focus),False,True)
                        c.capture_scene();u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),'bottle-close.png')
                # A small camera arc makes the moving reflection distinguishable from paint.
                pos,target=s['views'][name]
                t=0. if angles else max(0.,min(1.,(n-120)/240.));a=math.radians(20)*t*t*(3-2*t)
                dx,dy=pos[0]-target[0],pos[1]-target[1]
                eye=u.Vector(target[0]+dx*math.cos(a)-dy*math.sin(a),target[1]+dx*math.sin(a)+dy*math.cos(a),pos[2])
                c.get_owner().set_actor_location_and_rotation(eye,u.MathLibrary.find_look_at_rotation(eye,u.Vector(*target)),False,True)
                c.capture_scene()
                u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),name+'-buffer.png')
                payload=png_payload(out/(name+'-buffer.png'))
                p.stdin.write(payload)
                if full_splash and n in ((42,48,50,52,54,56,58,60,62,64,66,74,90,180,240,360) if landing else (42,180,360,420)):
                    (out/(name+'-check-'+str(n)+'.png')).write_bytes(payload)
            s['frames']+=1
        if n%60==0:
            amounts=[x.get_oil_amount() for x in spills]
            s['faded']|=any(0<a<.95 for a in amounts)
            s['rows'].append({'tick':n,'amounts':amounts,'spills':len(spills),'decals':decals,'flight_batches':flying,'sheets':sheets})
            if n in (120,180,360,660):
                u.SystemLibrary.execute_console_command(w,'Prophecy.Oil.Probe')
                if union:
                    p=json.loads((out.parents[1]/'probe.json').read_text(encoding='utf-8-sig'))
                    s['rows'][-1].update({k:p[k] for k in ['patches','coverage_groups','coverage_rebuilds','coverage_raster_ms']})
            (out/'progress.json').write_text(json.dumps({'tick':n,'frames':s['frames'],'elapsed':time.monotonic()-s['start']}))
        if n>=660:return finish('complete')
    except Exception:return finish(traceback.format_exc())

s['callback']=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
