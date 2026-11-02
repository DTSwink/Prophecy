"""Clear glass tuning + actual Jolt impact/break recording in the owned oil scene.
Only the glass material is saved. Fixture actors, camera and lighting are unsaved.
"""
raise RuntimeError("Superseded: use StudioReview.py in the owned -ProphecyOilStudio process. This old glass recipe must not be restored.")
import json,math,shutil,struct,subprocess,time,traceback,zlib
from pathlib import Path
import unreal as u
assert '-ProphecyOilClearReview' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Clear';out.mkdir(parents=True,exist_ok=True)
root='/Game/_mygame/OilBottle';lib=u.MaterialEditingLibrary
m=u.load_asset(root+'/Materials/M_OilBottleGlass');assert m
disk=Path(u.Paths.project_content_dir())/'_mygame/OilBottle/Materials/M_OilBottleGlass.uasset'
if not (out/'before-glass.uasset').exists():shutil.copy2(disk,out/'before-glass.uasset')
def node(cls,**props):
    n=lib.create_material_expression(m,cls)
    for k,v in props.items():n.set_editor_property(k,v)
    return n
# Reset only our generated glass material, preserving its public fragment-fade controls.
lib.delete_all_material_expressions(m)
m.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
m.set_editor_property('two_sided',False)
m.set_editor_property('translucency_lighting_mode',u.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
def scalar(name,value):return node(u.MaterialExpressionScalarParameter,parameter_name=name,default_value=value)
color=node(u.MaterialExpressionVectorParameter,parameter_name='Color',default_value=u.LinearColor(1,1,1,1))
lib.connect_material_property(color,'',u.MaterialProperty.MP_BASE_COLOR)
lib.connect_material_property(scalar('Roughness',.07),'',u.MaterialProperty.MP_ROUGHNESS)
lib.connect_material_property(scalar('Specular',.5),'',u.MaterialProperty.MP_SPECULAR)
opacity=node(u.MaterialExpressionCustom,code='float Facing=abs(dot(normalize(N),normalize(V))); return saturate(Base+pow(saturate(1-Facing),5)*0.22)*Fade;',output_type=u.CustomMaterialOutputType.CMOT_FLOAT1)
inputs={'Base':scalar('Opacity',.006),'N':node(u.MaterialExpressionPixelNormalWS),'V':node(u.MaterialExpressionCameraVectorWS),'Fade':scalar('FragmentOpacity',1)}
entries=[]
for name in inputs:
    e=u.CustomInput();e.set_editor_property('input_name',name);entries.append(e)
opacity.set_editor_property('inputs',entries)
for name,n in inputs.items():assert lib.connect_material_expressions(n,'',opacity,name)
lib.connect_material_property(opacity,'',u.MaterialProperty.MP_OPACITY)
lib.layout_material_expressions(m);lib.recompile_material(m)
u.SystemLibrary.execute_console_command(ed.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
assert u.EditorAssetLibrary.save_loaded_asset(m,False)
sheet=u.load_asset(root+'/VFX/M_OilDroplet')
(out/'materials.json').write_text(json.dumps({'glass':{'opacity':.006,'fresnel_edge_addition':.22,'two_sided':False,'roughness':.07,'inner_shell_abs_normal':True},
    'sheet':str(sheet),'sheet_emissive':str(lib.get_material_property_input_node(sheet,u.MaterialProperty.MP_EMISSIVE_COLOR)),
    'sheet_base':str(lib.get_material_property_input_node(sheet,u.MaterialProperty.MP_BASE_COLOR))},indent=2))
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
for a in actors.get_all_level_actors():
    if isinstance(a,u.ProphecyOilBottle):actors.destroy_actor(a)
base=u.Vector(-980,-380,70);floor=u.Vector(-980,-380,0)
bp=u.load_asset(root+'/BP_OilBottle')
a=actors.spawn_actor_from_class(bp.generated_class(),base);a.set_actor_label('ClearBottleReview');a.tags=['ClearBottleReview']
a.set_editor_property('launch_on_play',False);a.set_editor_property('break_on_hit',True)
a.bottle.set_simulate_physics(False);a.bottle.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
s={'tick':0,'world':None,'last':-1,'start':time.monotonic(),'rows':[],'break_tick':None,'max_fragments':0,'faded':False,'frames':0}
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
    s['bottle']=u.GameplayStatics.get_all_actors_with_tag(w,'ClearBottleReview')[0]
    a=spawn(w,u.SceneCapture2D,base+u.Vector(40,-80,65),base+u.Vector(0,0,12))
    c=a.get_component_by_class(u.SceneCaptureComponent2D);s['capture']=c
    c.capture_every_frame=False;c.capture_on_movement=False;c.always_persist_rendering_state=True
    c.capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR;c.fov_angle=45
    c.texture_target=u.RenderingLibrary.create_render_target2d(w,960,720,u.TextureRenderTargetFormat.RTF_RGBA8)
    log=(out/'encode.log').open('wb');s['encoder_log']=log
    s['encoder']=subprocess.Popen([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','png','-framerate','30','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','19','-threads','1','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'clear-bottle-break.mp4')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    for cmd in ['r.MotionBlurQuality 0','r.ScreenPercentage 100','t.MaxFPS 30']:u.SystemLibrary.execute_console_command(w,cmd)
def finish(reason):
    u.unregister_slate_post_tick_callback(s['callback'])
    p=s.get('encoder');exitcode=-1
    if p:p.stdin.close();exitcode=p.wait(timeout=30);s['encoder_log'].close()
    w=s['world'];last=s['rows'][-1] if s['rows'] else {}
    checks={'completed':reason=='complete','encoded':exitcode==0,'impact_break':s['break_tick'] is not None and s['break_tick']>180,
        '20_fragments':s['max_fragments']==20,'fragment_fade':s['faded'],'fragment_cleanup':last.get('fragments',-1)==0,
        'spill_seen':any(r['spills']>0 for r in s['rows'])}
    (out/'test.json').write_text(json.dumps({'reason':reason,'checks':checks,'break_tick':s['break_tick'],'rows':s['rows'],'frames':s['frames'],
        'source':'Actual UE/Jolt capture. First3sec held/moved, then physical release. No manual BreakBottle calls. Playback60 authored ticks/sec.'},indent=2))
    if w and ed.get_game_world()==w:level.editor_request_end_play()
    s.pop('capture',None);s.pop('bottle',None);s['world']=None
    print('CLEAR_BOTTLE_FINISHED',checks)
    # Keep this one owned process available for visual inspection / material iteration.
def tick(_):
    try:
        if time.monotonic()-s['start']>420:return finish('timeout')
        w=ed.get_game_world()
        if not w:return
        now=u.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now;s['world']=w;s['tick']+=1;n=s['tick']
        if n==1:init(w)
        bottles=u.GameplayStatics.get_all_actors_with_tag(w,'ClearBottleReview')
        a=bottles[0] if bottles else None
        if a and 30<n<=120:
            phase=(n-30)*2*math.pi/90
            a.set_actor_rotation(u.Rotator(18*math.sin(phase),0,12*math.sin(phase*2)),True)
        if n==180:
            assert a
            b=a.bottle;b.set_collision_profile_name('PhysicsActor');b.set_simulate_physics(True)
            b.set_physics_linear_velocity(u.Vector(110,0,-80),False)
            b.set_physics_angular_velocity_in_degrees(u.Vector(0,90,30),False)
            result=u.ProphecyJoltStaticMeshLibrary.enable_jolt_static_mesh_physics(b)
            assert u.ProphecyJoltStaticMeshLibrary.is_jolt_static_mesh_physics_enabled(b),str(result)
        if not a and s['break_tick'] is None:s['break_tick']=n
        pieces=u.GameplayStatics.get_all_actors_with_tag(w,'OilBottleFragment');s['max_fragments']=max(s['max_fragments'],len(pieces))
        if pieces:
            mat=pieces[0].static_mesh_component.get_material(0)
            if isinstance(mat,u.MaterialInstanceDynamic):s['faded']|=0<mat.get_scalar_parameter_value('FragmentOpacity')<.95
        if n%15==0:s['rows'].append({'tick':n,'bottle':a is not None,'fragments':len(pieces),'spills':len(u.GameplayStatics.get_all_actors_of_class(w,u.ProphecyOilSpill))})
        if n%2==0:
            c=s['capture'];t=max(0,min(1,(n-120)/60));t=t*t*(3-2*t)
            close_eye=base+u.Vector(40,-80,65);close_target=base+u.Vector(0,0,12)
            wide_eye=floor+u.Vector(110,-205,170);wide_target=floor+u.Vector(35,0,28)
            eye=close_eye*(1-t)+wide_eye*t;target=close_target*(1-t)+wide_target*t
            if s['break_tick']:
                p=max(0,min(1,(n-s['break_tick']-25)/60));p=p*p*(3-2*p)
                eye=eye*(1-p)+(floor+u.Vector(150,-320,260))*p;target=target*(1-p)+(floor+u.Vector(45,0,3))*p
            c.get_owner().set_actor_location_and_rotation(eye,u.MathLibrary.find_look_at_rotation(eye,target),False,True)
            c.capture_scene();u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),'buffer.png')
            data=payload(out/'buffer.png');s['encoder'].stdin.write(data);s['frames']+=1
            if n in [60,100,180,210,220,240,270,360,480]:(out/f'check-{n}.png').write_bytes(data)
        if n>=540:return finish('complete')
    except Exception:return finish(traceback.format_exc())
s['callback']=u.register_slate_post_tick_callback(tick);level.editor_request_begin_play()
