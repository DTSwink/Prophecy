"""Owned comparison of standard and coupled pike; no saved scene or Blueprint edits."""
import json, math, pathlib, re, sys, time, traceback, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'User Play left untouched'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CoupledPike'
out.mkdir(parents=True,exist_ok=True)
slide={'start':time.monotonic(),'world':None,'handle':None,'last':None,'samples':[], 'first':None}
mode=sys.argv[sys.argv.index('--solver')+1] if '--solver' in sys.argv else 'coupled'
assert mode in ('coupled','off')
tag='probe-'+mode
pike_library=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyPhysicsConstraintBlueprintLibrary'))
seen=set()
physics=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyJoltStandardPhysicsLibrary'))
def vec(v):return [v.x,v.y,v.z]
def tr(t):
    q=t.rotation
    return {'p':vec(t.translation),'q':[q.x,q.y,q.z,q.w],'s':vec(t.scale3d)}
def finish(error=None):
    unreal.unregister_slate_post_tick_callback(slide['handle'])
    if slide['world'] and ed.get_game_world()==slide['world']:le.editor_request_end_play()
    (out/(tag+'.json')).write_text(json.dumps({'error':error,'solver':mode,'samples':slide['samples']},indent=2))
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
                if c.get_path_name() not in seen:
                    assert pike_library.call_method('SetPikeWoundCorrection',(c,mode=='coupled'))
                    seen.add(c.get_path_name())
                comps=c.get_constrained_components()
                item={'name':c.get_name(),'transform':tr(c.get_world_transform()),'endpoints':str(comps),
                      'instance':c.get_editor_property('constraint_instance').export_text(),
                      'force':str(physics.call_method('GetConstraintForce',(c,))),'bodies':[],
                      'native_angles':[physics.call_method(n,(c,)) for n in ('GetCurrentTwist','GetCurrentSwing1','GetCurrentSwing2')]}
                for comp,bone in ((comps[0],comps[1]),(comps[2],comps[3])):
                    item['bodies'].append(tr(comp.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD)) if comp else None)
                row['joints'].append(item)
            if row['joints']:
                unreal.SystemLibrary.execute_console_command(w,'Prophecy.Jolt.ConstraintAudit A_Sword')
                row['native_audit']=json.loads((pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/StandardConstraints/World.json').read_text(encoding='utf-8-sig'))
            slide['samples'].append(row)
        if (slide['first'] is not None and t-slide['first']>1.2) or time.monotonic()-slide['began']>25:finish()
    except Exception:finish(traceback.format_exc())
slide['handle']=unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print('Owned solver comparison started: '+mode)


