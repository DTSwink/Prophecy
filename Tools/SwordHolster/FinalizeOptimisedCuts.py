"""Verify the installed graph, save only A_Sword, and retain a compact receipt."""
import hashlib, json, pathlib, runpy, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(), 'Active Play is preserved'
root=pathlib.Path(unreal.Paths.project_dir())
out=root/'Saved/Diagnostics/SwordOptimised'
runpy.run_path(str(root/'Tools/SwordHolster/InstallOptimisedCuts.py'))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Editor.LiveAgentTypes Inspect')
report=(root/'Saved/Diagnostics/LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in report and 'native_properties=0 pin_types=0' in report, report
old=json.loads((out/'restart-preservation.json').read_text())
map_path=root/'Content/explosionVFX.umap'
assert hashlib.sha256(map_path.read_bytes()).hexdigest()==old['hashes']['Content\\explosionVFX.umap']
bp=unreal.load_asset('/Game/_mygame/sword/A_Sword')
assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
receipt=dict(map=ed.get_editor_world().get_path_name(), play=False, saved=bp.get_path_name(),
    mode=unreal.get_default_object(bp.generated_class()).get_editor_property('Optimised'),
    hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [map_path,root/'Content/_mygame/sword/A_Sword.uasset']},
    dirty=[p.get_path_name() for p in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())],
    native='Live Coding loaded; normal DLLs need incremental build before cold launch')
(out/'final-state.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
