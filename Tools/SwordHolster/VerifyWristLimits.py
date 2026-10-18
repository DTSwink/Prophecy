"""Owned PIE: D/S frees the wrist through return and restores exact entry limits.

Only runtime instances are changed; no Blueprint, map or PHAT saves.
"""
import argparse
import json
import pathlib
import re
import time
import traceback
import unreal

p=argparse.ArgumentParser()
p.add_argument('--case',choices=['complete','hide_s_return','hide_d_return'],default='complete')
p.add_argument('--custom',action='store_true')
args=p.parse_args()
r=pathlib.Path(unreal.Paths.project_dir())
out=r/'Saved/Diagnostics/SwordWristLimits20261015';out.mkdir(parents=True,exist_ok=True)
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
le=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(),'Existing user Play is left untouched'
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
lib=unreal.ConstraintInstanceBlueprintLibrary
s=dict(world=None,last=-1,start=time.monotonic(),events=[],checks=0,returns={'S':0,'D':0},drawing=False)

def limits(actor):
    result={}
    for c in actor.get_pose_reference_mesh().get_constraints(True):
        bones=[str(x) for x in lib.get_attached_body_names(c)[1:]]
        result['|'.join(bones)]=[v.value if i%2==0 else v for i,v in enumerate(lib.get_angular_limits(c)[1:])]
    return result

def report(world,actor):
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Sword.HolsterReport')
    raw=(r/'Saved/Diagnostics/SwordDraw20261010/state.txt').read_bytes()
    text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    line=next(x for x in text.splitlines() if x.startswith(actor.get_name()+' '))
    return {k:float(v) for k,v in re.findall(r'(\w+)=(-?\d+(?:\.\d+)?)',line)}

def finish(reason):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if s['world'] and ed.get_game_world()==s['world']:le.editor_request_end_play()
    data={k:v for k,v in s.items() if k not in ['cb','world','start']}
    data.update(reason=reason,options=vars(args))
    name=args.case+('-custom' if args.custom else '')
    (out/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('WRIST_LIMITS_FINISHED',name,reason)

def tick(_):
    try:
        if time.monotonic()-s['start']>90:return finish('timeout')
        world=ed.get_game_world()
        if not world:
            if s['world']:return finish('world ended externally')
            return
        s['world']=world
        a=unreal.GameplayStatics.get_player_pawn(world,0)
        if not isinstance(a,unreal.ProphecyAgent):return
        n=int(a.get_editor_property('absolute tick debug'))
        if n==s['last']:return
        s['last']=n
        if n>=6 and not s.get('prepared'):
            assert n<29,'Missed fixture setup window'
            # Skip only this PIE instance's two-ball experiment; saved user setup is unchanged.
            assert not a.get_editor_property('bool debug 3'),'Expected current grab-review branch'
            a.set_editor_property('Left Grab Ball',None)
            a.set_editor_property('Right Grab Ball',None)
            s['prepared']=True
        if n<6:return
        f=report(world,a);phase=int(f['phase'])
        if 'before' not in s:
            # The current user graph starts S during initialization. Let it
            # finish before capturing entry values for our controlled D/S pair.
            if phase!=3:
                if n>300:return finish('Initial scene S did not finish')
                return
            assert a.is_jolt_physical_animation_enabled()
            if args.custom:
                error=a.set_physical_joint_angular_limits('hand_r',unreal.AngularConstraintMotion.ACM_LIMITED,17.,unreal.AngularConstraintMotion.ACM_LOCKED,11.,unreal.AngularConstraintMotion.ACM_FREE,8.)
                assert not error,error
            s['before']=limits(a)
            s['selected']=[k for k in s['before'] if set(k.split('|')) & {'neck_01','neck_02','head'} or set(k.split('|'))=={'hand_r','lowerarm_r'}]
            s['wrist']=next(k for k in s['selected'] if 'hand_r' in k.split('|'))
            s['events'].append([n,'Entry limits captured after scene S'])
            assert api.call_method('DrawSword',args=(a,False))
            s['drawing']=True
            return
        current=limits(a)
        active=phase in (0,1,2,4,5)
        for k,v in current.items():
            if active and k in s['selected']:
                assert v[::2]==[0,0,0],f'Active joint not free: {k} {v}'
                assert v[1::2]==s['before'][k][1::2],f'Angles changed: {k}'
            else:assert v==s['before'][k],f'Prior limits not preserved/restored: {k} {v}'
        s['checks']+=1
        action='D' if s['drawing'] else 'S'
        if s.get('phase')!=[action,phase]:s['events'].append([n,action,phase]);s['phase']=[action,phase]
        if phase==4:s['returns'][action]+=1
        if active and phase==4 and s['returns'][action]==3:
            assert api.call_method('DrawSword',args=(a,not s['drawing'])),'Repeated request rejected'
            assert limits(a)==current,'Repeated request changed limits'
        if phase==4 and s['returns'][action]>=5 and args.case==f'hide_{action.lower()}_return':
            a.hide_sword()
            assert limits(a)==s['before'],'Hide did not restore exact entry limits'
            s['after']=limits(a);s['events'].append([n,'Hide restored limits'])
            return finish('passed')
        if phase==3 and not s['drawing']:
            assert s['returns']['S']>5,'Missing S return coverage'
            s['events'].append([n,'S completed, exact limits restored'])
            s['after']=current
            return finish('passed')
        elif phase==-1 and s['drawing']:
            assert s['returns']['D']>5,'Missing D return coverage'
            s['events'].append([n,'D completed, exact limits restored'])
            assert api.call_method('DrawSword',args=(a,True))
            s['drawing']=False
        if n>650:return finish('stall')
    except Exception:return finish(traceback.format_exc())

s['cb']=unreal.register_slate_post_tick_callback(tick)
le.editor_request_begin_play()
print('WRIST_LIMITS_STARTED',vars(args))
