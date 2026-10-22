"""Load/check closest-agent node without starting Play or changing scene actors."""
import json
from pathlib import Path
import shutil
import sys
import unreal


def main():
    root = Path(unreal.Paths.project_dir())
    output = root / 'Saved/Diagnostics/ClosestAgent'
    output.mkdir(parents=True, exist_ok=True)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if '--build' in sys.argv:
        assert not editor.get_game_world(), 'Active user Play preserved'
        name = '/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
        dirty = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        for package in dirty:
            if package.get_path_name() == name:
                source = root / 'Content' / (name[6:] + '.uasset')
                backup = output / 'BP_ProphecyManualPoseAgent.before-save.uasset'
                if not backup.exists():
                    shutil.copy2(source, backup)
                assert unreal.EditorLoadingAndSavingUtils.save_packages([package], False)
                print('Preserved current agent Blueprint edits to disk before reload')
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'LiveCoding.Compile')
        return

    library = unreal.get_default_object(unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyReachLibrary'))
    assert unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyReachLibrary:GetClosestAgent')
    assert library.call_method('GetClosestAgent', args=(None,)) is None
    world = editor.get_game_world() or editor.get_editor_world()
    cls = unreal.load_class(None, '/Script/GameAnimationSample3.ProphecyAgent')
    agents = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
    results = []
    for agent in agents:
        others = [other for other in agents if other != agent]
        def distance_squared(other):
            delta = agent.get_actor_location() - other.get_actor_location()
            return delta.x*delta.x + delta.y*delta.y + delta.z*delta.z
        actual = library.call_method('GetClosestAgent', args=(agent,))
        if others:
            assert actual in others
            assert abs(distance_squared(actual) - min(map(distance_squared, others))) < 1e-6
        else:
            assert actual is None
        results.append(dict(agent=agent.get_name(), closest=actual.get_name() if actual else None))
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
    report = (root / 'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    if 'status=1 ' in report and 'native_properties=0 pin_types=0' in report:
        blueprint = unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
        unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
        report = (root / 'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    assert 'status=3' in report and 'native_properties=0 pin_types=0' in report, report
    result = dict(map=world.get_path_name(), play=bool(editor.get_game_world()), results=results,
                  null_input_pass=True, blueprint_types_valid=True,
                  dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
                         + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())])
    (output / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


main()
