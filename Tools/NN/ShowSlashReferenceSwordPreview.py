"""PIE-only follow camera/readback. Leave motion playing for the user."""
import json
from pathlib import Path
import time
import traceback
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() or unreal.EditorLevelLibrary.get_game_world()
assert world
data=json.loads((root/'Saved/SlashChain/sword_preview.json').read_text())
reference=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.SkeletalMeshActor)
               if a.get_actor_label()=='SlashChain30_Reference_Looping')
mesh=reference.get_component_by_class(unreal.SkeletalMeshComponent)
sword=next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.StaticMeshActor)
           if a.get_actor_label()=='SlashChain30_Sword').get_component_by_class(unreal.StaticMeshComponent)
arm=reference.call_method('AddComponentByClass',args=(unreal.SpringArmComponent.static_class(),False,unreal.Transform(),False))
arm.attach_to_component(mesh,'pelvis',unreal.AttachmentRule.SNAP_TO_TARGET,unreal.AttachmentRule.KEEP_WORLD,unreal.AttachmentRule.KEEP_WORLD,False)
arm.set_absolute(False,True,True)
arm.set_world_rotation(unreal.Rotator(-12,135,0),False,True)
arm.set_editor_property('target_arm_length',350.)
arm.set_editor_property('target_offset',unreal.Vector(0,0,35))
arm.set_editor_property('do_collision_test',False)
camera=reference.call_method('AddComponentByClass',args=(unreal.CameraComponent.static_class(),False,unreal.Transform(),False))
camera.attach_to_component(arm,'SpringEndpoint',unreal.AttachmentRule.SNAP_TO_TARGET,unreal.AttachmentRule.SNAP_TO_TARGET,unreal.AttachmentRule.SNAP_TO_TARGET,False)
camera.set_field_of_view(65)
unreal.GameplayStatics.get_player_controller(world,0).set_view_target_with_blend(reference,.25)
state={'handle':None,'samples':0,'max_forearm_mm':0.,'max_grip_mm':0.,'last':mesh.get_position(),'loops':0,'start':time.monotonic(),'shots':[]}
grip=sword.get_relative_transform()

def finish(error=None):
    unreal.unregister_slate_post_tick_callback(state['handle'])
    state['handle']=None
    report={k:v for k,v in state.items() if k not in ('handle','start','last')}
    report.update(error=error,passed=not error and state['max_forearm_mm']<.1 and state['max_grip_mm']<.1)
    (root/'Saved/SlashChain/sword_preview_live.json').write_text(json.dumps(report,indent=2))

def tick(delta):
    try:
        for hand,spec in data['clamp'].items():
            length=(mesh.get_socket_location(hand)-mesh.get_socket_location(hand.replace('hand','lowerarm'))).length()
            state['max_forearm_mm']=max(state['max_forearm_mm'],abs(length-spec['rest_cm'])*10)
        hand=mesh.get_socket_transform('hand_r',unreal.RelativeTransformSpace.RTS_WORLD)
        expected=unreal.MathLibrary.compose_transforms(grip,hand)
        state['max_grip_mm']=max(state['max_grip_mm'],(expected.translation-sword.get_world_location()).length()*10)
        position=mesh.get_position()
        if position<state['last']-.1: state['loops']+=1
        state['last']=position
        state['samples']+=1
        if state['samples'] in (60,150):
            path=root/f"Saved/SlashChain/sword_preview_{len(state['shots'])+1}.png"
            unreal.SystemLibrary.execute_console_command(world,f'HighResShot filename="{path.as_posix()}" 1280x720')
            state['shots'].append(str(path))
        if state['loops']>=2: finish()
        elif time.monotonic()-state['start']>60: finish('Loop test timed out')
    except Exception: finish(traceback.format_exc())

state['handle']=unreal.register_slate_post_tick_callback(tick)
print('Showing sword preview with a pelvis-following camera; no production camera changes.')
