"""Cross-bottle union, shared fade, owner removal and settled-mask regression."""
import json,time,traceback
from pathlib import Path
import unreal as u
assert '-ProphecyOilUnionCheck' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Union';out.mkdir(parents=True,exist_ok=True)
s={'tick':0,'time':-1,'world':None,'start':time.monotonic(),'rows':{},'checks':{}}
u.EditorPythonScripting.set_keep_python_script_alive(True)
def probe(w):
    u.SystemLibrary.execute_console_command(w,'Prophecy.Oil.Probe')
    r=json.loads((out.parent/'probe.json').read_text(encoding='utf-8-sig'))
    r['decals']=len(w.get_world_settings().get_components_by_class(u.DecalComponent))
    return r
def spill(w,x,y=-400):
    settings=u.ProphecyOilSettings(radius=60,slipperiness=1,hold_duration=.5,fade_duration=1.5,
        decal_material=u.load_asset('/Game/_mygame/Tests/Oil/M_OilPlaceholder'),tint_material=u.load_asset('/Game/_mygame/Tests/Oil/M_OilTint'))
    return u.ProphecyOilLibrary.spawn_oil_spill(w,u.Vector(x,y,0),u.Vector(0,0,1),settings)
def finish(reason):
    u.unregister_slate_post_tick_callback(s['callback'])
    if s['world'] and ed.get_game_world()==s['world']:level.editor_request_end_play()
    (out/'union-check.json').write_text(json.dumps({'reason':reason,'checks':s['checks'],'rows':s['rows']},indent=2))
    print('OIL_UNION_CHECK_FINISHED',reason,s['checks']);u.EditorPythonScripting.set_keep_python_script_alive(False)
def tick(_):
    try:
        if time.monotonic()-s['start']>240:return finish('timeout')
        w=ed.get_game_world()
        if not w:return
        t=u.GameplayStatics.get_time_seconds(w)
        if t==s['time']:return
        s['time']=t;s['world']=w;s['tick']+=1;n=s['tick']
        if n==660:
            s['checks']['initial_cleanup']=probe(w)['coverage_groups']==0
            s['a']=spill(w,-1100);assert s['a']
        if n==665:
            s['b']=spill(w,-1035);s['c']=spill(w,-1100,100);assert s['b'] and s['c']
        if n in (666,675,705,710,720,730,790,850):
            r=probe(w);s['rows'][n]={k:r[k] for k in ['patches','coverage_groups','coverage_stamps','coverage_rebuilds','coverage_raster_ms','decals']}
            if n==666:
                s['checks']['cross_actor_union']=r['coverage_groups']==2 and r['coverage_stamps']==3 and r['decals']==4
            if n==705:
                s['checks']['settled_mask_static']=r['coverage_rebuilds']==s['rows'][675]['coverage_rebuilds']
            if n==710:
                a=s['a'].get_oil_amount();b=s['b'].get_oil_amount()
                s['checks']['shared_fade']=0<a<1 and abs(a-b)<1e-6
            if n==720:s['checks']['survives_owner_removal']=r['coverage_groups']==2 and r['coverage_stamps']==2 and s['b'].get_oil_amount()>0
            if n==730:s['checks']['new_drop_refreshes_group']=s['b'].get_oil_amount()==1 and s['d'].get_oil_amount()==1 and r['coverage_groups']==2
            if n==790:s['checks']['disconnected_fades_independently']=r['coverage_groups']==1
            if n==850:
                s['checks']['complete_cleanup']=r['coverage_groups']==0 and r['patches']==0 and r['decals']==0
                return finish('complete')
        if n==715:s['a'].destroy_actor()
        if n==725:s['d']=spill(w,-1060);assert s['d']
    except Exception:return finish(traceback.format_exc())
s['callback']=u.register_slate_post_tick_callback(tick)
u.SystemLibrary.execute_console_command(ed.get_editor_world(),'t.MaxFPS 0')
level.editor_request_begin_play()
