"""Remove only the audited sword End Play clock reset and verify the graph diff."""
from pathlib import Path
import json
import shutil
import unreal


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert not editor.get_game_world(), 'User Play preserved'
    root = Path(unreal.Paths.project_dir())
    output = root / 'Saved/Diagnostics/SwordEndPlayFPS'
    output.mkdir(parents=True, exist_ok=True)
    blueprint = unreal.load_asset('/Game/_mygame/sword/A_Sword')
    source = root / 'Content/_mygame/sword/A_Sword.uasset'
    backup = output / 'A_Sword.before.uasset'
    if not backup.exists():
        shutil.copy2(source, backup)
    graph = root / 'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt'
    def audit():
        unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
        return graph.read_text(encoding='utf-16')
    before = audit()
    (output / 'graph-before.txt').write_text(before, encoding='utf-8')
    cap = unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS')
    unreal.SystemLibrary.execute_console_command(editor.get_editor_world(), 'Prophecy.Editor.RefreshHolsterGripPins RemoveSwordEndPlayFPS')
    after = audit()
    prefix = '/Game/_mygame/sword/A_Sword.A_Sword | EventGraph | '
    expected = []
    removed = 0
    for block in before.split('\n\n'):
        header = block.split('\n')[0]
        if header.startswith(prefix + 'K2Node_CallFunction_159 |') or header.startswith(prefix + 'ProphecyEndPlayCap |'):
            removed += 1
            continue
        if header.startswith(prefix + 'K2Node_Event_4 |'):
            block = block.replace(' -> K2Node_CallFunction_159.execute', ' ->')
        expected.append(block)
    assert removed == 2, 'Expected exactly two reset nodes'
    assert '\n\n'.join(expected) == after, 'Unexpected graph change; do not save'
    assert unreal.SystemLibrary.get_console_variable_float_value('t.MaxFPS') == cap
    assert unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=True)
    unreal.BlueprintEditorLibrary.refresh_open_editors_for_blueprint(blueprint)
    result = dict(removed_nodes=removed, other_wiring_unchanged=True, cap_unchanged=cap,
                  saved='/Game/_mygame/sword/A_Sword', play=False,
                  dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
                         + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())])
    (output / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


main()
