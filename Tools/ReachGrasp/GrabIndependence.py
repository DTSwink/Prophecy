"""Preserve/load/check per-arm grab independence without changing user tuning."""
import json
import re
import shutil
import sys
from pathlib import Path
import unreal


def main():
    root = Path(unreal.Paths.project_dir())
    out = root / 'Saved/Diagnostics/GrabIndependence'
    out.mkdir(parents=True, exist_ok=True)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert not editor.get_game_world(), 'Active user Play preserved'
    bp_path = '/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
    blueprint = unreal.load_asset(bp_path)
    graph = root / 'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'

    def command(text):
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), text)

    def audit():
        command('Prophecy.Sword.AuditCollisionGraph')
        return graph.read_text(encoding='utf-16')

    if '--build' in sys.argv:
        backup = out / 'agent-before-save.uasset'
        if not backup.exists():
            shutil.copy2(root / 'Content' / (bp_path[6:] + '.uasset'), backup)
        assert unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=True)
        (out / 'graph-before.txt').write_text(audit(), encoding='utf-8')
        command('LiveCoding.Compile')
        print('Agent edits preserved; Live Coding dispatched')
        return

    for name in ['GrabObject', 'GrabBone', 'SetGrabJointIndependence', 'GetGrabJointIndependence']:
        function = unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyReachLibrary:' + name)
        assert function and unreal.EditorAssetLibrary.get_metadata_tag(function, 'DefaultToSelf') == 'Agent', name
        if name != 'GetGrabJointIndependence':
            assert float(unreal.EditorAssetLibrary.get_metadata_tag(function, 'CPP_Default_JointIndependance')) == 0, name
    before = audit()
    command('Prophecy.Editor.LiveAgentTypes RefreshGrabIndependence')
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    after = audit()

    def normalize(text):
        text = re.sub(r'^  JointIndependance=0(?:\.0+)? None ->\n', '', text, flags=re.M)
        text = text.replace('\n  object=', '\n  Object=').replace('.object', '.Object')
        return re.sub(r'/Engine/Transient\.BPGC_ARCH_FOR_CDO_(\w+?)_\d+', r'/Script/GameAnimationSample3.Default__\1', text)

    assert normalize(before) == normalize(after), 'Unexpected graph change; do not save'
    grabs = [b for b in after.split('\n\n') if ' | Grab Bone\n' in b or ' | Grab Object\n' in b]
    assert grabs and all('JointIndependance=' in b for b in grabs), grabs
    command('Prophecy.Editor.LiveAgentTypes Inspect')
    report = (root / 'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    assert 'status=3' in report and 'native_properties=0 pin_types=0' in report, report
    assert unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=True)
    unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(blueprint)
    command('Prophecy.Reach.Inspect IndependenceMath')
    solver = (out / 'solver.txt').read_text(encoding='utf-8-sig')
    assert 'failures=0' in solver, solver
    result = dict(grab_nodes=len(grabs), graph_preserved=True, solver=solver.strip(), saved=bp_path)
    (out / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


main()
