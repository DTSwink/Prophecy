"""Moving half-attack target projection/latch observation, PIE NPC only."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal

world=unreal.EditorLevelLibrary.get_game_world()
assert world
agent=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent)
           if a.get_agent_handle().index==1)
saved_mode=agent.get_simulation_mode()
saved_tick=agent.is_actor_tick_enabled()
saved_input=agent.get_locomotion_input()
saved_override=agent.get_editor_property('use_blueprint_locomotion_input')
saved_radius=agent.call_method('GetGlobalHalfAttackTargetRadius')
agent.set_simulation_mode(unreal.ProphecyAgentSimulationMode.KINEMATIC)
agent.set_actor_tick_enabled(False)
agent.call_method('StopNNAttack')
agent.call_method('SetGlobalHalfAttackTargetRadius',args=(125.0,))
agent.set_locomotion_input(unreal.Vector(0,1,0),False,unreal.Vector(0,1,0),0.5,1)
half_test={'handle':None,'rows':[],'case':-1,'start_next':True,'deadline':time.monotonic()+20}


def xyz(v):return [v.x,v.y,v.z]


def finish(error=None):
    if half_test['handle'] is not None:
        unreal.unregister_slate_post_tick_callback(half_test['handle'])
        half_test['handle']=None
    agent.call_method('StopNNAttack')
    agent.call_method('SetGlobalHalfAttackTargetRadius',args=(saved_radius,))
    i=saved_input
    agent.set_locomotion_input(i.world_move_input,i.run,i.facing_world_direction,i.speed_scale,i.turn_scale)
    agent.set_editor_property('use_blueprint_locomotion_input',saved_override)
    agent.set_simulation_mode(saved_mode)
    agent.set_actor_tick_enabled(saved_tick)
    path=Path(unreal.Paths.project_saved_dir()).resolve()/'SlashParity/half_target_motion.json'
    path.write_text(json.dumps({'passed':error is None,'error':error,'rows':half_test['rows']},indent=2))
    print('Moving half target test:',path,'error=',error)


def tick(_dt):
    try:
        assert time.monotonic()<half_test['deadline'],'Timeout'
        names,future,_,_=agent.read_nn_future_world_pose()
        pelvis=future[[str(n) for n in names].index('pelvis')].translation
        if half_test['start_next']:
            half_test['case']+=1
            if half_test['case']==2:
                finish();return
            family=['slashL','pike'][half_test['case']]
            target=pelvis+unreal.Vector(40,500,35)
            assert agent.call_method('TriggerNNAttack',args=(unreal.Name(family),target,True))
            half_test['summary']={'family':family,'origin':xyz(agent.get_root_low_point()),'samples':0,
                                  'max_distance_cm':0,'hit_frame':None,'armed_frame':None}
            half_test['rows'].append(half_test['summary'])
            half_test['until']=unreal.GameplayStatics.get_time_seconds(world)+3
            half_test['start_next']=False
            return
        attack=agent.call_method('GetNNAttackState')
        summary=half_test['summary']
        if attack:
            assert attack[1]
            requested,effective,ghost=agent.call_method('GetNNAttackTarget')
            distance=math.dist(xyz(pelvis),xyz(effective))
            requested_distance=math.dist(xyz(pelvis),xyz(requested))
            assert abs(distance-min(125,requested_distance))<0.001,(distance,requested_distance)
            expected=pelvis+(requested-pelvis)*(min(1,125/requested_distance))
            assert math.dist(xyz(expected),xyz(effective))<0.001
            summary['samples']+=1
            summary['max_distance_cm']=max(summary['max_distance_cm'],distance)
            if attack[2] and summary['armed_frame'] is None:summary['armed_frame']=attack[-1]
            if attack[3] and summary['hit_frame'] is None:summary['hit_frame']=attack[-1]
        if not attack or unreal.GameplayStatics.get_time_seconds(world)>=half_test['until']:
            summary['root_travel_cm']=math.dist(summary['origin'],xyz(agent.get_root_low_point()))
            assert summary['samples']>5 and summary['root_travel_cm']>10,summary
            summary['natural_completion']=not bool(attack)
            agent.call_method('StopNNAttack')
            half_test['start_next']=True
    except Exception:
        finish(traceback.format_exc())


half_test['handle']=unreal.register_slate_post_tick_callback(tick)
print('Moving slashL/pike half-target check started')
