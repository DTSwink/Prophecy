"""Preserve and verify Blueprint Self defaults for all grab controls."""
import json
from pathlib import Path
import shutil
import sys
import unreal


def main():
    root = Path(unreal.Paths.project_dir())
    output = root / 'Saved/Diagnostics/GrabDefaultsSelf'
    output.mkdir(parents=True, exist_ok=True)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert not editor.get_game_world(), 'Active user Play preserved'
    path = '/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
    blueprint = unreal.load_asset(path)
    graph_path = root / 'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'
    def audit():
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
        return graph_path.read_text(encoding='utf-16')
    if '--build' in sys.argv:
        source = root / 'Content' / (path[6:] + '.uasset')
        backup = output / 'agent-before-save.uasset'
        if not backup.exists():
            shutil.copy2(source, backup)
        assert unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=True)
        (output / 'graph-before.txt').write_text(audit(), encoding='utf-8')
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'LiveCoding.Compile')
        print('Agent edits preserved; build dispatched')
        return
    names = ['GrabObject', 'GrabBone', 'ReleaseGrab', 'GetGrabStatus',
             'SetGrabAngleTolerances', 'GetGrabAngleTolerances']
    for name in names:
        function = unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyReachLibrary:' + name)
        assert function and unreal.EditorAssetLibrary.get_metadata_tag(function, 'DefaultToSelf') == 'Agent', name
    before = audit()
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes GrabDefaultsToSelf')
    after = audit()
    expected = []
    for block in before.split('\n\n'):
        header = block.split('\n')[0]
        if '| tick debugging | K2Node_CallFunction_304 |' in header:
            block = block.replace('  Agent= None -> K2Node_CallFunction_305.ReturnValue', '  Agent= None ->')
        elif '| tick debugging | K2Node_CallFunction_305 |' in header:
            block = block.replace(' K2Node_CallFunction_304.Agent', '')
        expected.append(block)
    # ReconstructNode canonicalizes this legacy FName's casing; its links do not change.
    def canonical(text):
        return text.replace('\n  object=', '\n  Object=').replace('K2Node_CallFunction_302.object', 'K2Node_CallFunction_302.Object')
    assert canonical('\n\n'.join(expected)) == canonical(after), 'Other graph changes detected; do not save'
    grab = next(b for b in after.split('\n\n') if '| tick debugging | K2Node_CallFunction_304 |' in b)
    assert '\n  Agent= None ->\n' in grab
    assert 'Mesh= None -> K2Node_CallFunction_307.ReturnValue' in grab
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
    report = (root / 'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    assert 'status=3' in report and 'native_properties=0 pin_types=0' in report, report
    assert unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=True)
    unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(blueprint)
    result = dict(default_to_self=names, grabber_self=True, victim_mesh_preserved=True,
                  other_wiring_unchanged=True, saved=path, play=False)
    (output / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


main()
