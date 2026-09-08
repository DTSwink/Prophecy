"""Constant identical hand force distinguishes native arm strength1 from0.5."""
import unreal,time,math,json,traceback
from pathlib import Path
w=unreal.EditorLevelLibrary.get_game_world()
a=next(x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if x.get_name()=='NativePhysicalTest')
m=a.get_agent_mesh();saved_i=a.get_locomotion_input();saved_nn=a.is_nn_inference_enabled()
saved_c=a.get_editor_property('bNativeContacts');saved_g=a.get_editor_property('bNativeGravity')
saved_fps=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
a.stop_locomotion_input();a.call_method('SetNativeContactsAndGravity',args=(False,False))
unreal.SystemLibrary.execute_console_command(w,'t.MaxFPS 60')
strength_test={'handle':None,'phase':-1,'deadline':time.monotonic()+3,'rows':[],'summary':[],'game_time':None}
def finish(error=None):
    if strength_test['handle'] is not None:unreal.unregister_slate_post_tick_callback(strength_test['handle']);strength_test['handle']=None
    a.call_method('SetNativeBodyStrengthBelow',args=('upperarm_r',1.,1.,True))
    a.call_method('SetNativeContactsAndGravity',args=(saved_c,saved_g));a.set_nn_inference_enabled(saved_nn)
    i=saved_i;a.set_locomotion_input(i.world_move_input,i.run,i.facing_world_direction,i.speed_scale,i.turn_scale)
    unreal.SystemLibrary.execute_console_command(w,f't.MaxFPS {saved_fps}')
    path=Path(unreal.Paths.project_saved_dir()).resolve()/'NativePhysical/strength.json'
    path.write_text(json.dumps({'passed':error is None,'error':error,'summary':strength_test['summary'],'rows':strength_test['rows']},indent=2))
    print('Native strength force test',path,error)
def tick(_dt):
    try:
        game_time=unreal.GameplayStatics.get_time_seconds(w)
        if game_time==strength_test['game_time']:return
        strength_test['game_time']=game_time
        now=time.monotonic();phase=strength_test['phase']
        if phase>=0:
            target,actual,*_=a.call_method('GetNativeBodySample',args=('hand_r',))
            delta=actual.translation-target.translation
            strength_test['rows'].append({'phase':phase,'time':now,'game_time':game_time,'error':[delta.x,delta.y,delta.z]})
            m.add_force(unreal.Vector(100000,0,0),'hand_r',False)
        if now<strength_test['deadline']:return
        if phase>=0:
            rows=[r for r in strength_test['rows'] if r['phase']==phase];tail=rows[len(rows)//2:]
            strength_test['summary'].append({'phase':phase,'scale':[1,.5,1][phase],'n':len(tail),
                'mean_error':[sum(r['error'][i] for r in tail)/len(tail) for i in range(3)]})
        phase+=1;strength_test['phase']=phase;strength_test['deadline']=now+3
        if phase==3:
            full,half,restored=strength_test['summary']
            assert half['mean_error'][0]>full['mean_error'][0]*1.2,'Half strength did not increase compliance under identical force'
            assert abs(restored['mean_error'][0]-full['mean_error'][0])<max(.1,abs(full['mean_error'][0])*.15),'Strength1 did not restore compliance'
            finish();return
        a.set_nn_inference_enabled(False)
        assert a.call_method('SetNativeBodyStrengthBelow',args=('upperarm_r',[1.,.5,1.][phase],[1.,.5,1.][phase],True))>=3
    except Exception:finish(traceback.format_exc())
strength_test['handle']=unreal.register_slate_post_tick_callback(tick)
print('Native identical-force strength test started')
