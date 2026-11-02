"""Owned real Jolt Play: soft/strong impacts, opt-outs, material inheritance, fade/cleanup."""
import json,time,traceback,runpy
from pathlib import Path
import unreal as u
assert '-ProphecyOilBottleCheck' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
out=Path(u.Paths.project_saved_dir())/'Diagnostics/Oil/Bottle'
bp=u.load_asset('/Game/_mygame/OilBottle/BP_OilBottle');actors=u.get_editor_subsystem(u.EditorActorSubsystem)
cdo=u.get_default_object(bp.generated_class());component=cdo.get_editor_property('bottle')
defaults={'launch_on_play':cdo.get_editor_property('launch_on_play'),'break_impact_speed':cdo.break_impact_speed,
    'fragment_count':len(cdo.fragment_meshes),'fragment_velocity':cdo.fragment_velocity,'fragment_lifetime':cdo.fragment_lifetime,
    'fragment_fade_duration':cdo.fragment_fade_duration,'mesh':component.static_mesh.get_path_name(),'splash':cdo.oil.splash_system.get_path_name()}
assert not defaults['launch_on_play'] and defaults['fragment_count']==20
(out/'defaults.json').write_text(json.dumps(defaults,indent=2))
for name,y,z,auto,frags in [('Soft',200,2,True,True),('NoFragments',500,180,True,False),('Manual',800,180,False,False)]:
    a=actors.spawn_actor_from_class(bp.generated_class(),u.Vector(-1100,y,z));a.set_actor_label('BottleTest_'+name);a.tags=['BottleTest_'+name]
    a.set_editor_property('launch_on_play',False);a.set_editor_property('break_on_hit',auto);a.set_editor_property('spawn_fragments',frags)
s={'start':time.monotonic(),'world':None,'tick':0,'last':-1,'rows':[],'errors':[],'max_pieces':0,'material_checked':False,'override_inherited':False,'faded':False,'manual_survived':False}
u.EditorPythonScripting.set_keep_python_script_alive(True)
def finish(reason):
    u.unregister_slate_post_tick_callback(s['callback'])
    w=ed.get_game_world()
    if w and w==s['world']:level.editor_request_end_play()
    last=s['rows'][-1] if s['rows'] else {}
    checks={'completed':reason=='complete','soft_survived':last.get('soft',False),'manual_waited':s['manual_survived'],
        'exactly_40_fragments':s['max_pieces']==40,'material_inheritance':s['material_checked'],'live_override_inheritance':s['override_inherited'],
        'fade_seen':s['faded'],'fragment_cleanup':last.get('fragments',-1)==0,
        'oil_cleanup':last.get('spills',-1)==0,'hard_and_manual_consumed':last.get('bottles',-1)==1}
    (out/'test.json').write_text(json.dumps({'reason':reason,'checks':checks,'rows':s['rows'],'errors':s['errors']},indent=2))
    print('OIL_BOTTLE_TEST',checks)
    if all(checks.values()) and '-ProphecyOilBottleVideo' in u.SystemLibrary.get_command_line():
        def next_stage(_):
            if ed.get_game_world():return
            u.unregister_slate_post_tick_callback(s['next'])
            for a in actors.get_all_level_actors():
                if a.get_actor_label().startswith('BottleTest_'):actors.destroy_actor(a)
            runpy.run_path(str(Path(u.Paths.project_dir())/'Tools/Oil/RecordVideo.py'),run_name='__main__')
        s['next']=u.register_slate_post_tick_callback(next_stage)
        return
    u.EditorPythonScripting.set_keep_python_script_alive(False)
    u.SystemLibrary.quit_editor()
def tick(_):
    try:
        if time.monotonic()-s['start']>360:return finish('timeout')
        w=ed.get_game_world()
        if not w:return
        now=u.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now;s['world']=w;s['tick']+=1;n=s['tick']
        bottles=u.GameplayStatics.get_all_actors_of_class(w,u.ProphecyOilBottle)
        if n==1:
            a=next(a for a in bottles if a.get_actor_label()=='Oil_Bottle_Mesh')
            mid=a.get_editor_property('bottle').create_dynamic_material_instance(0)
            mid.set_vector_parameter_value('Color',u.LinearColor(.1,.7,.2,1))
        pieces=u.GameplayStatics.get_all_actors_with_tag(w,'OilBottleFragment')
        s['max_pieces']=max(s['max_pieces'],len(pieces))
        soft=next((a for a in bottles if a.actor_has_tag('BottleTest_Soft')),None)
        manual=next((a for a in bottles if a.actor_has_tag('BottleTest_Manual')),None)
        if n==120:
            s['manual_survived']=manual is not None
            if manual:manual.break_bottle(manual.get_actor_location(),u.Vector(0,0,1))
        if pieces and not s['material_checked']:
            for a in pieces:
                c=a.static_mesh_component
                for slot in range(2):
                    m=c.get_material(slot);assert m and isinstance(m,u.MaterialInstanceDynamic)
                    parent=m.get_editor_property('parent')
                    while isinstance(parent,u.MaterialInstanceDynamic):parent=parent.get_editor_property('parent')
                    assert parent.get_name()==('M_OilBottleGlass' if slot==0 else 'M_OilBottleCork')
            s['material_checked']=True
        if pieces and not s['override_inherited']:
            for a in pieces:
                color=a.static_mesh_component.get_material(0).get_vector_parameter_value('Color')
                s['override_inherited']|=abs(color.r-.1)<.001 and abs(color.g-.7)<.001
        if pieces:
            m=pieces[0].static_mesh_component.get_material(0)
            value=m.get_scalar_parameter_value('FragmentOpacity')
            s['faded']|=0<value<.95
        if n%30==0:
            s['rows'].append({'tick':n,'bottles':len(bottles),'soft':soft is not None,'soft_impact':soft.last_impact_speed if soft else None,
                'fragments':len(pieces),'spills':len(u.GameplayStatics.get_all_actors_of_class(w,u.ProphecyOilSpill))})
        if n in [60,180,360,720]:
            u.SystemLibrary.execute_console_command(w,'Prophecy.Oil.Probe')
            p=json.loads((out.parent/'probe.json').read_text(encoding='utf-8-sig'))
            (out/f'probe-{n}.json').write_text(json.dumps(p,indent=2))
            assert not p['faulted'];assert p['landscape_bodies']>0
            assert p['coverage_groups']<=8,'Oil must not allocate a separate coating per debris shard'
        if n>=720:return finish('complete')
    except Exception:return finish(traceback.format_exc())
s['callback']=u.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
