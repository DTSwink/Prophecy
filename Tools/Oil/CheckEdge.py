"""Owned, unsaved material comparison at a frozen oil landing pose."""
import json, math, time, traceback
from pathlib import Path
import unreal as u

assert '-ProphecyOilEdge' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Edge'
out.mkdir(parents=True,exist_ok=True)
lib=u.MaterialEditingLibrary
material=u.load_asset('/Game/_mygame/Tests/Oil/M_OilPlaceholder')
mask=lib.get_material_property_input_node(material,u.MaterialProperty.MP_OPACITY)
assert isinstance(mask,u.MaterialExpressionCustom)
original=mask.get_editor_property('code')
prefix=original[:original.index('return ')]
variants=[('before',prefix+'return saturate((edge-length(p))/0.035)*Amount;'),
    ('soft12',prefix+'return smoothstep(0.0,0.12,edge-length(p))*Amount;'),
    ('soft06',prefix+'return smoothstep(0.0,0.06,edge-length(p))*Amount;'),
    ('aa',prefix+'float d=edge-length(p); float w=max(fwidth(d),0.001); return smoothstep(-w*0.5,w*0.5,d)*Amount;'),
    ('hard',prefix+'return step(0.0175,edge-length(p))*Amount;'),
    ('narrow',prefix+'return smoothstep(0.0165,0.0185,edge-length(p))*Amount;')]
u.EditorPythonScripting.set_keep_python_script_alive(True)
s={'world':None,'tick':0,'last':-1,'stage':-1,'age':0,'start':time.monotonic(),'captures':[]}

def finish(reason):
    u.unregister_slate_post_tick_callback(s['callback'])
    if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
    (out/'comparison.json').write_text(json.dumps({'reason':reason,'tick':s['tick'],'variants':variants,'saved':False},indent=2))
    print('OIL_EDGE_FINISHED',reason)
    u.EditorPythonScripting.set_keep_python_script_alive(False)

def capture_init(w):
    gs=u.get_default_object(u.GameplayStatics)
    for name,pos,target in [('mesh',(-1300,-780,310),(-960,-380,25)),('landscape',(270,-610,340),(710,-210,10))]:
        a=math.radians(10);dx,dy=pos[0]-target[0],pos[1]-target[1]
        eye=u.Vector(target[0]+dx*math.cos(a)-dy*math.sin(a),target[1]+dx*math.sin(a)+dy*math.cos(a),pos[2])
        tr=u.Transform(location=eye,rotation=u.MathLibrary.find_look_at_rotation(eye,u.Vector(*target)))
        actor=gs.call_method('BeginDeferredActorSpawnFromClass',(w,u.SceneCapture2D,tr,u.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
        actor=gs.call_method('FinishSpawningActor',(actor,tr,u.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
        c=actor.get_component_by_class(u.SceneCaptureComponent2D)
        c.capture_every_frame=False;c.capture_on_movement=False
        c.set_editor_property('always_persist_rendering_state',True)
        c.capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR;c.fov_angle=65
        c.texture_target=u.RenderingLibrary.create_render_target2d(w,1280,720,u.TextureRenderTargetFormat.RTF_RGBA8)
        s['captures'].append((name,c))
    for cmd in ['r.ScreenPercentage 100','r.MotionBlurQuality 0','t.MaxFPS 0']:
        u.SystemLibrary.execute_console_command(w,cmd)

def tick(_):
    try:
        if time.monotonic()-s['start']>240:return finish('timeout')
        w=ed.get_game_world()
        if not w:return
        s['world']=w
        if s['stage']<0:
            now=u.GameplayStatics.get_time_seconds(w)
            if now==s['last']:return
            s['last']=now;s['tick']+=1
            if s['tick']==1:capture_init(w)
            if s['tick']<240:return
            u.GameplayStatics.set_game_paused(w,True)
            s['stage']=0
        s['age']+=1
        if s['age']==1:
            mask.set_editor_property('code',variants[s['stage']][1]);lib.recompile_material(material)
            u.SystemLibrary.execute_console_command(w,'Editor.AsyncAssetCompilationFinishAll')
        # Warm capture history after each shader change; no game/physics motion.
        for _,c in s['captures']:c.capture_scene()
        if s['age']==90:
            for name,c in s['captures']:
                u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),variants[s['stage']][0]+'-'+name+'.png')
            s['age']=0;s['stage']+=1
            if s['stage']==len(variants):return finish('complete')
    except Exception:return finish(traceback.format_exc())

s['callback']=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
