"""Temporary PIE-only PHAT limit probes; restores every constraint afterward."""
import unreal, time, math, json, traceback
from pathlib import Path
w=unreal.EditorLevelLibrary.get_game_world()
a=next(x for x in unreal.GameplayStatics.get_all_actors_of_class(w,unreal.ProphecyAgent) if x.get_name()=='NativePhysicalTest')
m=a.get_agent_mesh(); lib=unreal.ConstraintInstanceBlueprintLibrary
constraints=m.get_constraints(False)
saved_limits=[(c,lib.get_angular_limits(c)[1:],lib.get_linear_limits(c)[1:]) for c in constraints]
saved_i=a.get_locomotion_input(); saved_nn=a.is_nn_inference_enabled()
saved_contacts=a.get_editor_property('bNativeContacts'); saved_g=a.get_editor_property('bNativeGravity')
saved_fps=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
a.call_method('SetNativeContactsAndGravity',args=(False,False))
a.set_nn_inference_enabled(True)
a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(0,1,0),1,1)
unreal.SystemLibrary.execute_console_command(w,'t.MaxFPS 30')
joint_probe={'handle':None,'phase':0,'deadline':time.monotonic()+5,'rows':[],'summary':[]}
names=['pelvis','calf_l','calf_r','foot_l','foot_r','lowerarm_l','lowerarm_r','hand_l','hand_r']
def restore_limits():
    for c,ang,lin in saved_limits:
        lib.set_angular_limits(c,*ang);lib.set_linear_limits(c,*lin)
def finish(error=None):
    if joint_probe['handle'] is not None:unreal.unregister_slate_post_tick_callback(joint_probe['handle']);joint_probe['handle']=None
    restore_limits()
    a.call_method('SetNativeContactsAndGravity',args=(saved_contacts,saved_g))
    a.set_nn_inference_enabled(saved_nn)
    i=saved_i;a.set_locomotion_input(i.world_move_input,i.run,i.facing_world_direction,i.speed_scale,i.turn_scale)
    unreal.SystemLibrary.execute_console_command(w,f't.MaxFPS {saved_fps}')
    path=Path(unreal.Paths.project_saved_dir()).resolve()/'NativePhysical/joint_probe.json'
    path.write_text(json.dumps({'error':error,'summary':joint_probe['summary'],'rows':joint_probe['rows']},indent=2))
    print('Joint limit probe',path,error)
def tick(dt):
    try:
        now=time.monotonic(); phase=joint_probe['phase']
        if now>joint_probe['deadline']-3:
            row={'phase':phase,'bodies':{}}
            for n in names:
                target,actual,*_=a.call_method('GetNativeBodySample',args=(n,))
                qa=actual.rotation;qt=target.rotation
                dot=abs(qa.x*qt.x+qa.y*qt.y+qa.z*qt.z+qa.w*qt.w)
                p=actual.translation;t=target.translation
                row['bodies'][n]=[math.dist([p.x,p.y,p.z],[t.x,t.y,t.z]),math.degrees(2*math.acos(min(1,dot)))]
            joint_probe['rows'].append(row)
        if now<joint_probe['deadline']:return
        rows=[r for r in joint_probe['rows'] if r['phase']==phase]
        joint_probe['summary'].append({'phase':phase,'n':len(rows),'body_means':{n:[sum(r['bodies'][n][i] for r in rows)/len(rows) for i in range(2)] for n in names}})
        phase+=1;joint_probe['phase']=phase;joint_probe['deadline']=now+5
        if phase==1:
            free=unreal.AngularConstraintMotion.ACM_FREE
            for c in constraints:lib.set_angular_limits(c,free,0,free,0,free,0)
        elif phase==2:
            free=unreal.LinearConstraintMotion.LCM_FREE
            for c in constraints:
                _,parent,child=lib.get_attached_body_names(c)
                if str(child) in ('hand_l','hand_r'):lib.set_linear_limits(c,free,free,free,0)
        else:finish()
    except Exception:finish(traceback.format_exc())
joint_probe['handle']=unreal.register_slate_post_tick_callback(tick)
print('Joint baseline/angular-free/wrist-free probe started; all settings restored afterward')
