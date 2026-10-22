"""Read-only reflection check after loading the reach pelvis-height nodes."""
import json
from pathlib import Path
import unreal


def verify():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    library = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyReachLibrary'))
    for name in ('SetReachMinimumPelvisHeight', 'GetReachMinimumPelvisHeight'):
        assert unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyReachLibrary:' + name), name
    default = library.call_method('GetReachMinimumPelvisHeight', args=(None,))
    assert default == 40.0, default
    assert not library.call_method('SetReachMinimumPelvisHeight', args=(None, 40.0))
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
    root = Path(unreal.Paths.project_dir())
    report = (root / 'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    assert 'status=3' in report and 'native_properties=0 pin_types=0' in report, report
    result = dict(default_cm=default, nodes_present=True, blueprint_types_valid=True,
                  play=bool(editor.get_game_world()), map=editor.get_editor_world().get_path_name(),
                  dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
                         + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())])
    (root / 'Saved/Diagnostics/ReachPelvisHeight/reflection.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


verify()
