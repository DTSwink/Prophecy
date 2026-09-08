"""PIE-only native drive contact A/B. Run after the main native audit finishes."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal

world=unreal.EditorLevelLibrary.get_game_world()
agent=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.ProphecyAgent)
           if a.get_name()=='NativePhysicalTest')
saved_input=agent.get_locomotion_input()
saved_inference=agent.is_nn_inference_enabled()
saved_contacts=agent.get_editor_property('bNativeContacts')
saved_gravity=agent.get_editor_property('bNativeGravity')
saved_fps=unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
gs=unreal.get_default_object(unreal.GameplayStatics)
transform=unreal.Transform(location=unreal.Vector(10000,1500,2200),scale=unreal.Vector(.2,.2,.2))
block=gs.call_method('BeginDeferredActorSpawnFromClass',args=(world,unreal.StaticMeshActor.static_class(),
    transform,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
block_mesh=block.static_mesh_component
block_mesh.set_mobility(unreal.ComponentMobility.MOVABLE)
block_mesh.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
block_mesh.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
block_mesh.set_collision_object_type(unreal.CollisionChannel.ECC_WORLD_STATIC)
block_mesh.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
gs.call_method('FinishSpawningActor',args=(block,transform,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
agent.stop_locomotion_input()
agent.call_method('SetNativeContactsAndGravity',args=(False,False))
unreal.SystemLibrary.execute_console_command(world,'t.MaxFPS 60')
native_contact_test={'handle':None,'phase':-1,'deadline':time.monotonic()+2,'rows':[],'stages':[]}

def xyz(v):return [v.x,v.y,v.z]

def finish(error=None):
    if native_contact_test['handle'] is not None:
        unreal.unregister_slate_post_tick_callback(native_contact_test['handle'])
        native_contact_test['handle']=None
    block.destroy_actor()
    agent.call_method('SetNativeContactsAndGravity',args=(saved_contacts,saved_gravity))
    agent.set_nn_inference_enabled(saved_inference)
    i=saved_input
    agent.set_locomotion_input(i.world_move_input,i.run,i.facing_world_direction,i.speed_scale,i.turn_scale)
    unreal.SystemLibrary.execute_console_command(world,f't.MaxFPS {saved_fps}')
    path=Path(unreal.Paths.project_saved_dir()).resolve()/'NativePhysical/contacts.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'passed':error is None,'error':error,'stages':native_contact_test['stages'],
        'rows':native_contact_test['rows']},indent=2))
    print('Native physical contact A/B',path,'error',error)

def tick(_dt):
    try:
        now=time.monotonic()
        phase=native_contact_test['phase']
        sample=agent.call_method('GetNativeBodySample',args=('hand_r',))
        if sample:
            target,actual,v,omega,mass,blend=sample
            assert blend==1
            native_contact_test['rows'].append({'phase':phase,'time':now,'target':xyz(target.translation),
                'actual':xyz(actual.translation),'error_cm':math.dist(xyz(actual.translation),xyz(target.translation)),
                'root':xyz(agent.get_root_low_point())})
        if now<native_contact_test['deadline']:return
        if phase>=0:
            rows=[r for r in native_contact_test['rows'] if r['phase']==phase]
            tail=rows[len(rows)//2:]
            native_contact_test['stages'].append({'phase':phase,'samples':len(rows),
                'mean_error_cm':sum(r['error_cm'] for r in tail)/len(tail),'last':rows[-1]})
        phase+=1
        native_contact_test['phase']=phase
        native_contact_test['deadline']=now+2
        if phase==0:
            agent.set_nn_inference_enabled(False)
            block.set_actor_location(target.translation,False,True)
            block_mesh.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        elif phase==1:
            agent.call_method('SetNativeContactsAndGravity',args=(True,False))
        elif phase==2:
            agent.call_method('SetNativeContactsAndGravity',args=(False,False))
        else:
            baseline,contact,recovery=native_contact_test['stages']
            assert contact['mean_error_cm']>baseline['mean_error_cm']+2, 'Blocking contact did not displace the real hand'
            assert recovery['mean_error_cm']<baseline['mean_error_cm']+1, 'Hand failed to return after removing contact'
            assert math.dist(baseline['last']['root'],contact['last']['root'])<0.1,'Capsule moved; not an isolated hand contact'
            assert math.dist(baseline['last']['target'],contact['last']['target'])<0.1,'Authored target moved during contact test'
            finish()
    except Exception:
        finish(traceback.format_exc())

native_contact_test['handle']=unreal.register_slate_post_tick_callback(tick)
print('Native hand contact A/B started')
