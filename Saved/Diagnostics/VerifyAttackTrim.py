import unreal
import json
from pathlib import Path

world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cls=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyAttackTrimLibrary')
assert cls, 'Missing trim library'
fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyAttackTrimLibrary:SetTrimAttack')
assert fn, 'Missing Set Trim Attack function'
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
agent=actors.spawn_actor_from_class(unreal.ProphecyAgent,unreal.Vector(0,0,-10000),transient=True)
lib=unreal.get_default_object(cls)
results={}
try:
    results['zeros']=lib.call_method('SetTrimAttack',args=(agent,*([0]*16)))
    for i in range(16):
        values=[0]*16
        values[i]=1
        results['family_'+str(i)]=lib.call_method('SetTrimAttack',args=(agent,*values))
    results['negative_rejected']=not lib.call_method('SetTrimAttack',args=(agent,-1,*([0]*15)))
    results['clear']=lib.call_method('SetTrimAttack',args=(agent,*([0]*16)))
    assert all(results.values()), results
finally:
    actors.destroy_actor(agent)
results['play_active']=bool(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world())
if not results['play_active']:
    bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.SystemLibrary.execute_console_command(world,'Prophecy.Editor.LiveAgentTypes Inspect')
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.Attack.Trim')
(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/AttackTrimValidation.json').write_text(json.dumps(results,indent=2))
print('ATTACK_TRIM_VALIDATION',results)
