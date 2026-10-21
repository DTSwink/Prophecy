"""Inspect or refresh only the native node's display metadata; no graph edits."""
import hashlib, json, pathlib, sys, unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
fn = unreal.find_object(None, '/Script/ProphecyJolt.ProphecyJoltHitImpactLibrary:AcceptPikeHit')
assert fn
if '--apply' in sys.argv:
    bp = unreal.load_asset('/Game/_mygame/sword/A_Sword')
    def export_digest():
        path = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/CleanPike/rename-export.txt'
        t = unreal.AssetExportTask()
        t.object, t.filename, t.exporter = bp, str(path), unreal.ObjectExporterT3D()
        t.automated, t.prompt, t.replace_identical = True, False, True
        assert unreal.Exporter.run_asset_export_task(t)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.unlink()
        return digest
    before = export_digest()
    unreal.EditorAssetLibrary.set_metadata_tag(fn, 'DisplayName', 'Cancel Hit Reaction')
    assert unreal.EditorAssetLibrary.get_metadata_tag(fn, 'DisplayName') == 'Cancel Hit Reaction'
    after = export_digest()
    assert before == after, 'Blueprint changed unexpectedly'
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(), 'Prophecy.Sword.AuditCollisionGraph')
    receipt = {'before_export_sha256': before, 'after_export_sha256': after,
        'function': fn.get_path_name(), 'display_name': 'Cancel Hit Reaction', 'saved_assets': False,
        'source_display_name_updated': True, 'build': False, 'restart': False}
    (pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/CleanPike/rename.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps({'play': bool(ed.get_game_world()),
    'display_name': unreal.EditorAssetLibrary.get_metadata_tag(fn, 'DisplayName'),
    'dirty': [x.get_path_name() for x in list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
              + list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())]}))
