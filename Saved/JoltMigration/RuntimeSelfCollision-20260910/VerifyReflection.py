import json
from pathlib import Path
import unreal

assert not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).is_in_play_in_editor()
agent_class = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyAgent')
agent = unreal.get_default_object(agent_class)
calls = {
    'SetJoltSelfCollisionEnabled': (False,),
    'SetJoltBodiesSelfCollisionEnabled': (['hand_l'], False),
    'SetJoltSelfCollisionBelow': ('upperarm_l', False, True),
    'SetJoltBodyPairSelfCollisionEnabled': ('hand_l', 'head', False),
    'ResetJoltSelfCollision': (),
    'GetJoltBodyPairSelfCollisionEnabled': ('hand_l', 'head'),
}
results = {}
for name, args in calls.items():
    # Use current Unreal reflection, including functions added since Python's glue was generated.
    result = agent.call_method(name, args=args)
    results[name] = result
folder = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/RuntimeSelfCollision-20260910'
(folder / 'reflection.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results))
