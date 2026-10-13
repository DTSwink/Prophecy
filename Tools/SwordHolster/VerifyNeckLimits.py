"""Owned-PIE D/S neck-limit lifetime checks. No asset writes or tuning saves."""
import argparse
import json
import pathlib
import re
import time
import traceback
import unreal

parser=argparse.ArgumentParser()
parser.add_argument('--action',choices=['complete','hide','drop','mode','sword_destroy','reset'],default='complete')
parser.add_argument('--phase',type=int,choices=[1,2,4],default=1)
parser.add_argument('--drawing',action='store_true')
parser.add_argument('--custom',action='store_true')
parser.add_argument('--contacts',action='store_true',help='Verify temporary head/clavicle exclusions and retained user preferences too')
parser.add_argument('--output',default='Saved/Diagnostics/SwordNeckLimits20261011')
args=parser.parse_args()
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world(),'Existing Play is left untouched.'
root=pathlib.Path(unreal.Paths.project_dir())
preset=json.loads((root/'Content/locomotion/SwordHolsterProfile.json').read_text())['parameters']
speeds=tuple(float(preset[k]) for k in ['maxReachSpeed','maxReachRotationSpeed','slidingSpeed'])
out=root/args.output
out.mkdir(parents=True,exist_ok=True)
api=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecySwordHolsterLibrary'))
lib=unreal.ConstraintInstanceBlueprintLibrary
state=dict(world=None,last=-1,start=time.monotonic(),checks=0,events=[],drawing=False)

def check_contacts(world):
    # Existing read-only native probe reports unique scoped pairs, independently
    # of PHAT/user self-collision preferences. No extra runtime instrumentation.
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Reach.Inspect -713')
    raw=(root/'Saved/Diagnostics/ReachGrasp20261012/native--713.csv').read_bytes()
    text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    actual=int(text.splitlines()[0].split(',')[3])
    state['contact_checks']=state.get('contact_checks',0)+1
    return actual


def limits(actor):
    result={}
    for c in actor.get_pose_reference_mesh().get_constraints(True):
        bones=[str(x) for x in lib.get_attached_body_names(c)[1:]]
        values=lib.get_angular_limits(c)[1:]
        result['|'.join(bones)]=[v.value if i%2==0 else v for i,v in enumerate(values)]
    return result

def report(world,actor):
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Sword.HolsterReport')
    raw=(root/'Saved/Diagnostics/SwordDraw20261010/state.txt').read_bytes()
    text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    line=next(x for x in text.splitlines() if x.startswith(actor.get_name()+' '))
    return {k:float(v) for k,v in re.findall(r'(\w+)=(-?\d+(?:\.\d+)?)',line)}

def finish(reason):
    unreal.unregister_slate_post_tick_callback(state['callback'])
    if state['world'] and editor.get_game_world()==state['world']:level.editor_request_end_play()
    result={k:v for k,v in state.items() if k not in ['world','callback','start','sword']}
    result.update(reason=reason,options=vars(args))
    name=f"{args.action}-{args.phase}-{'draw' if args.drawing else 'sheathe'}{'-custom' if args.custom else ''}"
    (out/(name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('NECK_LIMITS_FINISHED',name,reason)

def tick(_):
    try:
        if time.monotonic()-state['start']>120:return finish('timeout')
        world=editor.get_game_world()
        if not world:
            if state['world']:finish('world ended externally')
            return
        state['world']=world
        actor=unreal.GameplayStatics.get_player_pawn(world,0)
        if not isinstance(actor,unreal.ProphecyAgent):return
        n=int(actor.get_editor_property('absolute tick debug'))
        if n==state['last']:return
        state['last']=n
        if n>=6 and 'before' not in state and actor.is_jolt_physical_animation_enabled():
            if args.custom:
                for bone,angles in [('neck_01',(17.,11.,8.)),('neck_02',(19.,12.,7.)),('head',(24.,13.,9.))]:
                    error=actor.set_physical_joint_angular_limits(bone,unreal.AngularConstraintMotion.ACM_LIMITED,angles[0],unreal.AngularConstraintMotion.ACM_LOCKED,angles[1],unreal.AngularConstraintMotion.ACM_FREE,angles[2])
                    assert not error,error
            state['before']=limits(actor)
            state['selected']=[k for k in state['before'] if set(k.split('|')) & {'neck_01','neck_02','head'}]
            assert state['selected']
            state['sword']=actor.get_held_sword()
            if args.contacts:
                for other in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent):
                    if other!=actor:other.hide_sword()
                state['contact_counts']=[]
                if args.custom:
                    assert not actor.set_jolt_body_pair_self_collision_enabled('head','clavicle_l',False)
                state['contact_preferences']=[str(actor.get_jolt_body_pair_self_collision_enabled('head',b)) for b in ['clavicle_l','clavicle_r']]
            if args.action=='reset':
                result=unreal.ProphecyAgentResetLibrary.initialize_agent_reset(world)
                state['reset_init']=str(result)
        if n<25 or 'before' not in state:return
        f=report(world,actor);phase=int(f['phase']);current=limits(actor)
        if args.contacts:
            count=check_contacts(world)
            counts=state['contact_counts']
            if not counts or counts[-1][1:]!=[phase,count]:counts.append([n,phase,count])
            if phase==3 and len(counts)>1 and counts[-2][1]==4:
                assert counts[-2][2]-count==2,'Head/clavicle pairs not released at S completion'
            if actor.is_jolt_physical_animation_enabled():
                assert state['contact_preferences']==[str(actor.get_jolt_body_pair_self_collision_enabled('head',b)) for b in ['clavicle_l','clavicle_r']],'User collision preferences changed'
        if state.get('interrupted'):
            # Reset is queued to the next manager timer boundary; unlike Hide,
            # accepting its request does not synchronously rebuild the rig.
            if args.action=='reset' and phase!=-1 and n<=state['interrupted']+2:return
            if args.action=='mode':
                if phase==-1:state['cancelled_at_boundary']=n
                elif not state.get('cancelled_at_boundary') and n<=state['interrupted']+2:return
            assert current==state['before'],f'Limits not restored: {current}'
            if n>=state['interrupted']+5:
                new_kinematic=args.action=='mode' and state.get('cancelled_at_boundary') and f['kinematic']==1 and f['pose_tick']<=n-state['interrupted']
                assert (phase==-1 or new_kinematic) and f['joint']==0,(phase,f)
                state['after']=current
                return finish('passed')
            return
        active=phase in (0,1,2,4,5)
        for key,value in current.items():
            if active and key in state['selected']:
                assert value[::2]==[0,0,0],f'Active neck not free: {key} {value}'
                assert value[1::2]==state['before'][key][1::2],'Stored angles changed'
            else:assert value==state['before'][key],f'Unexpected limit change: {key} {value}'
        state['checks']+=1
        if args.action!='complete' and state['drawing']==args.drawing and phase==args.phase:
            state['events'].append([n,args.action,phase])
            if args.action=='hide':actor.hide_sword()
            elif args.action=='drop':assert actor.drop_sword()
            elif args.action=='sword_destroy':state['sword'].destroy_actor()
            elif args.action=='mode':assert actor.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
            elif args.action=='reset':
                result=unreal.ProphecyAgentResetLibrary.reset_initial_agents(world)
                state['reset_result']=str(result)
            state['interrupted']=n
            if args.action not in ('sword_destroy','reset'):assert limits(actor)==state['before'],'Limits not restored synchronously'
            return
        if phase==3 and not state['drawing']:
            state['events'].append([n,'S complete, limits restored'])
            state['drawing']=True
            assert api.call_method('DrawSword',args=(actor,False,*speeds))
        elif phase==-1 and state['drawing']:
            state['events'].append([n,'D complete, limits restored'])
            state['after']=current
            return finish('passed')
        if n>650:finish('stall')
    except Exception:finish(traceback.format_exc())

state['callback']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
print('NECK_LIMITS_STARTED',vars(args))
