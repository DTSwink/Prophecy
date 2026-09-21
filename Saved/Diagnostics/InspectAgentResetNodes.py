import json
from pathlib import Path
import unreal

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
before = editor.get_game_world()
cls = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyAgentResetLibrary')
assert cls is not None, 'Reset Blueprint library not loaded'
cdo = unreal.get_default_object(cls)
results = {}
for name in ('InitializeAgentReset', 'ResetInitialAgents'):
    result = cdo.call_method(name, (None,))
    # UE Python unwraps bool-success functions with output pins to None on failure.
    assert result is None or (isinstance(result, tuple) and result[0] is False), (name, result)
    results[name] = {'loaded': True, 'invalid_world_rejected': True, 'python_result': result}
    print(name, 'loaded; invalid world rejected:', result)
assert editor.get_game_world() == before, 'PIE world changed'
results['pie_preserved'] = True
Path(unreal.Paths.project_saved_dir(), 'Diagnostics', 'AgentResetNodes.json').write_text(json.dumps(results, indent=2))
