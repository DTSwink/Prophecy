"""Apply the verified rim correction to the oil coating only; preserve all tuning."""
import hashlib, json, shutil
from pathlib import Path
import unreal as u

assert '-ProphecyOilEdge' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Edge'
out.mkdir(parents=True,exist_ok=True)
disk=Path(u.Paths.project_content_dir()).resolve()/'_mygame/Tests/Oil/M_OilPlaceholder.uasset'
backup=out/'M_OilPlaceholder-before.uasset'
if not backup.exists():shutil.copy2(disk,backup)
lib=u.MaterialEditingLibrary
m=u.load_asset('/Game/_mygame/Tests/Oil/M_OilPlaceholder')
mask=lib.get_material_property_input_node(m,u.MaterialProperty.MP_OPACITY)
assert isinstance(mask,u.MaterialExpressionCustom)
before=mask.get_editor_property('code')
old='return saturate((edge-length(p))/0.035)*Amount;'
new='return step(0.0175,edge-length(p))*Amount;'
assert old in before or new in before
after=before.replace(old,new)
mask.set_editor_property('code',after)
lib.recompile_material(m)
u.SystemLibrary.execute_console_command(ed.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
assert lib.get_material_property_input_node(m,u.MaterialProperty.MP_BASE_COLOR) is None
assert lib.get_material_property_input_node(m,u.MaterialProperty.MP_NORMAL) is None
assert u.EditorAssetLibrary.save_loaded_asset(m)
(out/'applied.json').write_text(json.dumps({'before':before,'after':after,'asset':m.get_path_name(),
    'sha256':hashlib.sha256(disk.read_bytes()).hexdigest(),'only_coating_saved':True},indent=2))
print('OIL_EDGE_APPLIED')
if '-ProphecyOilVideo' in u.SystemLibrary.get_command_line():
    exec((Path(u.Paths.project_dir())/'Tools/Oil/RecordVideo.py').read_text(),{})
