import json
from datetime import datetime
from pathlib import Path
import unreal

folder = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/SwordHull-20260910'
applied = folder / 'applied.json'
captured = folder / 'prepared_before_save.json'
published = folder / 'publication.json'
assert not applied.exists() and not captured.exists() and not published.exists()
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert world
mesh = unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01_Training')
assert mesh
unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncStaticMeshCompilationFinishAll')
scratch = Path.home() / '.codex/tmp/ProphecyJolt' / ('SwordHull-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
scratch.mkdir(parents=True, exist_ok=False)
scratch_job = scratch / 'job.json'
scratch_applied = scratch / 'applied.json'
scratch_capture = scratch / 'prepared.json'
scratch_job.write_text((folder / 'job.json').read_text())
# Unreal's WithArgs console tokenizer does not preserve quoted whitespace paths.
unreal.SystemLibrary.execute_console_command(world,
    'Prophecy.Sword.ApplyTrainingHull ' + scratch_job.as_posix() + ' ' + scratch_applied.as_posix())
assert scratch_applied.exists(), 'Hull command did not produce a report'
applied.write_text(scratch_applied.read_text(encoding='utf-8-sig'))
result = json.loads(applied.read_text())
assert result.get('success'), result
assert result['source_render_materials_complex_query_unchanged'] and result['cooked_simple_hull_valid']
unreal.SystemLibrary.execute_console_command(world,
    'Prophecy.Jolt.CaptureTrainingSword ' + scratch_capture.as_posix())
assert scratch_capture.exists(), 'Native capture report missing'
captured.write_text(scratch_capture.read_text(encoding='utf-8-sig'))
capture = json.loads(captured.read_text())
assert capture.get('success'), capture.get('error')
mesh = unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01_Training')
assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=True)
published.write_text(json.dumps({'success': True, 'asset_saved': mesh.get_path_name(),
    'saved_only_training_asset': True, 'source_render_materials_complex_query_unchanged': True,
    'jolt_preparation_passed_before_save': True,
    'cooked_hull_vertices': result['after']['cooked_vertices_per_convex'],
    'authored_hull_vertices': result['after']['authored_vertices_per_convex'],
    'native_mass_kg': capture['mass_kg'], 'native_principal_inertia_kg_cm2': capture['principal_inertia_kg_cm2']}, indent=2))
print('SWORD_HULL_PUBLICATION_SUCCESS ' + str(published))
