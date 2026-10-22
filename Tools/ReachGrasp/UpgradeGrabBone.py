"""Preserve and verify the optional Grab Bone surface-point pin."""
import json
from pathlib import Path
import shutil
import sys
import unreal


def main():
    root = Path(unreal.Paths.project_dir())
    out = root / 'Saved/Diagnostics/GrabBoneSurface'
    out.mkdir(parents=True, exist_ok=True)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert not editor.get_game_world(), 'Active Play preserved'
    blueprint_path = '/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
    graph_file = root / 'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'
    if '--build' in sys.argv:
        for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
            if package.get_path_name() == blueprint_path:
                source = root / 'Content' / (blueprint_path[6:] + '.uasset')
                backup = out / 'agent-before-save.uasset'
                if not backup.exists():
                    shutil.copy2(source, backup)
                assert unreal.EditorLoadingAndSavingUtils.save_packages([package], False)
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
        shutil.copy2(graph_file, out / 'graph-before.txt')
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'LiveCoding.Compile')
        print('Agent edits preserved; build dispatched')
        return
    function = unreal.find_object(None, '/Script/GameAnimationSample3.ProphecyReachLibrary:GrabBone')
    assert unreal.EditorAssetLibrary.get_metadata_tag(function, 'CPP_Default_UseSurfacePoint') == 'true'
    blueprint = unreal.load_asset(blueprint_path)
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes RefreshGrabBone')
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
    before = (out / 'graph-before.txt').read_text(encoding='utf-16')
    after = graph_file.read_text(encoding='utf-16')
    grabs = [block for block in after.split('\n\n') if ' | Grab Bone\n' in block]
    assert grabs and all('UseSurfacePoint=true None ->' in block for block in grabs), grabs
    # The only permitted graph difference is the added pin (and remapped CDO name).
    import re
    def normalized(text):
        text = re.sub(r'^  UseSurfacePoint=true None ->\n', '', text, flags=re.M)
        return re.sub(r'/Engine/Transient\.BPGC_ARCH_FOR_CDO_(\w+?)_\d+', r'/Script/GameAnimationSample3.Default__\1', text)
    assert normalized(before) == normalized(after), 'Unexpected graph difference; do not save'
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
    report = (root / 'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
    assert 'status=3' in report and 'native_properties=0 pin_types=0' in report, report
    assert unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=True)
    unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(blueprint)
    result = dict(grab_nodes=len(grabs), default_use_surface_point=True, wiring_preserved=True,
                  blueprint_types_valid=True, map=editor.get_editor_world().get_path_name())
    (out / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


main()
