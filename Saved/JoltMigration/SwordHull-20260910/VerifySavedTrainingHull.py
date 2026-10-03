import json
from datetime import datetime
from pathlib import Path
import unreal

folder = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/SwordHull-20260910'
source = json.loads((folder / 'source.json').read_text())
folder = folder / 'VerifyNoMACD'
folder.mkdir(exist_ok=False)
mesh = unreal.load_asset(source['asset'])
assert mesh
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, 'Editor.AsyncStaticMeshCompilationFinishAll')
description = mesh.get_static_mesh_description(0)
vertices = []
for i in range(description.get_vertex_count()):
    p = description.get_vertex_position(unreal.VertexID(i))
    vertices.append([p.x, p.y, p.z])
assert vertices == source['vertices_cm'], 'Saved source vertices changed'
materials = [str(x.material_interface.get_path_name()) if x.material_interface else ''
             for x in mesh.get_editor_property('static_materials')]
assert materials == source['materials'], 'Saved materials changed'
scratch = Path.home()/'.codex/tmp/ProphecyJolt'/('SwordVerify-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
scratch.mkdir(parents=True, exist_ok=False)
for command, name in [('Prophecy.Jolt.CaptureTrainingSword', 'cold_capture'), ('Prophecy.Jolt.SwordFixture', 'sword_fixture')]:
    path = scratch / (name + '.json')
    target = folder / (name + '.json')
    assert not target.exists()
    unreal.SystemLibrary.execute_console_command(world, command + ' ' + path.as_posix())
    assert path.exists(), command + ' produced no report'
    target.write_text(path.read_text(encoding='utf-8-sig'))
    result = json.loads(target.read_text())
    assert result.get('success'), result.get('error')
(folder/'cold_verification.json').write_text(json.dumps({'success':True, 'source_vertices_unchanged':True,
    'materials_unchanged':True, 'saved_asset_jolt_preparation_passed':True, 'actual_sword_fixture_passed':True,
    'assets_saved':False}, indent=2))
print('SWORD_HULL_COLD_VERIFY_SUCCESS')
