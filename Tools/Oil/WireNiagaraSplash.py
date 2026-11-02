"""Assign only the oil lab's spray slot, preserving all existing oil tuning."""
import json
from pathlib import Path
import unreal as u
assert '-ProphecyOilNiagaraSetup' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
root='/Game/_mygame/Tests/Oil';ns=u.load_asset(root+'/NS_OilDroplets');assert ns
bp=u.load_asset(root+'/BP_OilBottle');cdo=u.get_default_object(bp.generated_class())
def assign(obj):
    obj.modify()
    old=obj.get_editor_property('oil')
    settings=u.ProphecyOilSettings(radius=old.radius,slipperiness=old.slipperiness,
        hold_duration=old.hold_duration,fade_duration=old.fade_duration,
        decal_material=old.decal_material,tint_material=old.tint_material,
        droplet_material=old.droplet_material,droplet_count=old.droplet_count,splash_system=ns)
    obj.set_editor_property('oil',settings)
    assert obj.get_editor_property('oil').splash_system==ns
assign(cdo)
u.BlueprintEditorLibrary.compile_blueprint(bp)
assert u.EditorAssetLibrary.save_loaded_asset(bp,False)
rows=[]
for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
    if isinstance(a,u.ProphecyOilBottle):assign(a);rows.append(a.get_actor_label())
assert len(rows)==2
assert u.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(),root+'/M_OilTest')
(Path(u.Paths.project_saved_dir())/'Diagnostics/Oil/NiagaraFlower/wired.json').write_text(json.dumps(rows))
u.SystemLibrary.quit_editor()
