"""Owned Play cut-frame capture; optional transient iteration or wound-anchor trials."""
import json, math, pathlib, re, sys, time, traceback, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'User Play left untouched'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeSlide'
out.mkdir(parents=True,exist_ok=True)
slide={'start':time.monotonic(),'world':None,'handle':None,'last':None,'samples':[], 'first':None}
iterations = int(sys.argv[sys.argv.index('--iterations')+1]) if '--iterations' in sys.argv else 0
tag = 'probe-iterations-'+str(iterations) if iterations else 'probe'
project_wound = '--project-wound' in sys.argv
if project_wound: tag='probe-wound-anchor'
physics=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary'))
def vec(v):return [v.x,v.y,v.z]
def tr(t):
    q=t.rotation
    return {'p':vec(t.translation),'q':[q.x,q.y,q.z,q.w],'s':vec(t.scale3d)}
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def rotate(q,v):
    c=cross(q[:3],v);d=cross(q[:3],[c[i]+q[3]*v[i] for i in range(3)])
    return [v[i]+2*d[i] for i in range(3)]
def frame_pos(text,name):return [float(x) for x in re.search(name+r'=\(X=([^,]+),Y=([^,]+),Z=([^\)]+)\)',text).groups()]
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(slide['handle'])
    if slide['world'] and ed.get_game_world()==slide['world']:le.editor_request_end_play()
    (out/(tag+'.json')).write_text(json.dumps({'error':error,'iterations':iterations,'samples':slide['samples']},indent=2))
def tick(dt):
    try:
        w=ed.get_game_world()
        if not w:
            if slide['world'] or time.monotonic()-slide['start']>30:finish('Play ended/startup timeout')
            return
        if not slide['world']:slide['world']=w;slide['began']=time.monotonic()
        t=unreal.GameplayStatics.get_time_seconds(w)
        if slide['last']==t:return
        slide['last']=t
        for a in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor):
            if not a.get_class().get_name().startswith('A_Sword_C'):continue
            sword=next(c for c in a.get_components_by_class(unreal.StaticMeshComponent) if c.get_name().lower()=='sword')
            cuts=a.get_editor_property('cuts')
            row={'t':t,'sword':tr(sword.get_world_transform()),'cuts':[c.export_text() for c in cuts],'joints':[]}
            if cuts and slide['first'] is None:slide['first']=t
            for c in a.get_components_by_class(unreal.PhysicsConstraintComponent):
                if c.get_name()=='dont':continue
                comps=c.get_constrained_components()
                item={'name':c.get_name(),'transform':tr(c.get_world_transform()),'endpoints':str(comps),
                      'instance':c.get_editor_property('constraint_instance').export_text(),
                      'force':str(physics.call_method('GetConstraintForce',(c,))),'bodies':[],
                      'native_angles':[physics.call_method(n,(c,)) for n in ('GetCurrentTwist','GetCurrentSwing1','GetCurrentSwing2')]}
                for comp,bone in ((comps[0],comps[1]),(comps[2],comps[3])):
                    item['bodies'].append(tr(comp.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD)) if comp else None)
                if project_wound and comps[2]==sword and len(cuts)==1:
                    a1,a2=item['bodies']
                    r1=rotate(a1['q'],frame_pos(item['instance'],'Pos1'))
                    r2=rotate(a2['q'],frame_pos(item['instance'],'Pos2'))
                    delta=[a1['p'][i]+r1[i]-a2['p'][i]-r2[i] for i in range(3)]
                    axis=rotate(a2['q'],[0,0,1])
                    axial=sum(delta[i]*axis[i] for i in range(3))
                    shift=[delta[i]-axial*axis[i] for i in range(3)]
                    assert all(math.isfinite(x) for x in shift)
                    item['projection_cm']=shift
                    item['before_projection_sword']=row['sword']
                    p=sword.get_world_location()
                    sword.set_world_location(unreal.Vector(p.x+shift[0],p.y+shift[1],p.z+shift[2]),False,True)
                    row['sword']=tr(sword.get_world_transform())
                    item['bodies'][1]=row['sword']
                row['joints'].append(item)
                if iterations and not slide.get('changed'):
                    victim=comps[0]
                    assert isinstance(victim,unreal.SkeletalMeshComponent)
                    p=victim.get_socket_location('hand_r')
                    suffix=' at %.9f %.9f %.9f'%(p.x,p.y,p.z)
                    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment iterations 10 '+str(iterations)+suffix)
                    unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ContactExperiment capture pikeslide_'+str(iterations)+suffix)
                    slide['changed']=True
                    row['iteration_intervention']=iterations
            if row['joints']:
                unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ConstraintAudit A_Sword')
                row['native_audit']=json.loads((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/StandardConstraints/World.json').read_text(encoding='utf-8-sig'))
            slide['samples'].append(row)
        if (slide['first'] is not None and t-slide['first']>1.2) or time.monotonic()-slide['began']>25:finish()
    except Exception:finish(traceback.format_exc())
slide['handle']=unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print('Owned cut-joint read-only probe started')
