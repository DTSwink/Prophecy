"""Transient PIE regression: corrected policy endpoints retain leg/torso topology.
No asset saves. Runtime-only setup is discarded when PIE ends.
"""
import builtins, json, math, pathlib, time, traceback, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Stop PIE before running this test'
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyPelvisInertiaLibrary'))
s=dict(start=time.monotonic(),last=-1,n=0,samples=0,max_errors={},phases=[])
builtins._pelvis_leg_chain_test=s
pairs=[('pelvis','thigh_l'),('pelvis','thigh_r'),('thigh_l','calf_l'),('thigh_r','calf_r'),
       ('calf_l','foot_l'),('calf_r','foot_r'),('pelvis','spine_01')]
contract=json.loads(pathlib.Path(unreal.Paths.project_content_dir(),'locomotion/NN/prophecy_slash_native.json').read_text())
attack_lengths={n:math.dist(v,[0,0,0])*100 for n,v in zip(contract['bone_names'],contract['lower_geometry']['local_offsets'])}
def xyz(v): return [v.x,v.y,v.z]
def set_(a,on,h=1.,v=1.,y=1.,p=1.):
    assert lib.call_method('SetPelvisInertia',(a,on,h,v,y,p,False))
def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/PelvisLegChain.json').write_text(
        json.dumps({k:v for k,v in s.items() if k not in ('cb','actor','baseline')},indent=2),encoding='utf-8')
    print('PELVIS_LEG_CHAIN',reason)
    if ed.get_game_world(): unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
def tick(_):
    try:
        if time.monotonic()-s['start']>240:
            s['result']='timeout'; finish(s['result']); return
        w=ed.get_game_world()
        if not w:return
        a=unreal.GameplayStatics.get_player_pawn(w,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        now=unreal.GameplayStatics.get_time_seconds(w)
        if now==s['last']:return
        s['last']=now;s['n']+=1;n=s['n']
        if n==10:
            a.set_actor_tick_enabled(False);a.stop_nn_attack()
            a.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            a.set_locomotion_input(unreal.Vector(),False,unreal.Vector(),1.,0.)
            set_(a,True,.3,.3,.3,.3)
            s['phases'].append('Kinematic, four inertia factors 0.3')
        if n==60:
            a.set_locomotion_input(unreal.Vector(0,1,0),True,unreal.Vector(),1.,0.)
            s['phases'].append('Run with inertia')
        if n==300:
            a.set_locomotion_input(unreal.Vector(1,0,0),False,unreal.Vector(),1.,0.)
            set_(a,True,0.,1.,0.,1.)
            s['phases'].append('World horizontal/yaw coast during turn')
        if n==600:
            a.set_locomotion_input(unreal.Vector(),False,unreal.Vector(),1.,0.)
            set_(a,True,.5,.5,.5,.5)
            s['phases'].append('Stop/recover with inertia')
        if n==820:
            a.stop_nn_attack()
            assert a.trigger_nn_attack('hookR',a.get_actor_location()+a.get_actor_forward_vector()*150.,False)
            s['phases'].append('Full hookR with corrected lower state before attack upper inference')
        if n==1060:
            a.stop_nn_attack()
            assert a.trigger_nn_attack('hookL',a.get_actor_location()+a.get_actor_forward_vector()*150.,True)
            s['phases'].append('Half hookL with locomotion pelvis/legs')
        if 40<=n<=1290:
            poses={}
            for name in {x for pair in pairs for x in pair}:
                poses[name]=a.get_authored_body_world_target(name)[1]
            lengths={p+'>'+c:math.dist(xyz(poses[p].translation),xyz(poses[c].translation)) for p,c in pairs}
            if 'baseline' not in s:s['baseline']=lengths
            for key,value in lengths.items():
                # Attack and locomotion exports have distinct measured thigh lengths
                # (right: 39.003277 cm vs 38.865063 cm). Check either actual contract.
                err=min(abs(value-s['baseline'][key]),abs(value-attack_lengths[key.split('>')[1]]))
                s['max_errors'][key]=max(err,s['max_errors'].get(key,0.))
                assert err<.02, (key,'bone length changed (cm)',err)
            for p,c in [('pelvis','thigh_l'),('pelvis','thigh_r'),('pelvis','spine_01')]:
                # Half attacks intentionally preserve their independent upper mount
                # rotation. Its offset can rotate relative to the lower pelvis;
                # the attachment distance above must still remain fixed.
                if n>=1060 and c=='spine_01':continue
                local=xyz(poses[p].inverse_transform_location(poses[c].translation))
                key=p+'>'+c+' local offset'
                if key not in s['baseline']:s['baseline'][key]=local
                err=math.dist(local,s['baseline'][key]);s['max_errors'][key]=max(err,s['max_errors'].get(key,0.))
                assert err<.02,(key,'detached relative to pelvis',err)
            s['samples']+=1
        if n==1300:
            set_(a,False)
            s['result']='passed';finish(s['result'])
    except Exception:
        s['result']=traceback.format_exc();finish(s['result'])
s['cb']=unreal.register_slate_post_tick_callback(tick)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
