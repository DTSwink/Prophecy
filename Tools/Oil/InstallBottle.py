"""Create/organize only Oil Bottle assets in an owned isolated editor."""
import json,traceback,runpy
from pathlib import Path
import unreal as u
assert '-ProphecyOilBottleSetup' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
out=Path(u.Paths.project_saved_dir())/'Diagnostics/Oil/Bottle';out.mkdir(parents=True,exist_ok=True)
root='/Game/_mygame/OilBottle';old='/Game/_mygame/Tests/Oil'
lib=u.MaterialEditingLibrary;assets=u.AssetToolsHelpers.get_asset_tools()
success=False
try:
    glass,cork,liquid=runpy.run_path(str(Path(__file__).with_name('BottleMaterials.py')))['build_materials'](False)
    u.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Oil.BakeBottle')
    mesh=u.load_asset(root+'/Meshes/SM_OilBottle');assert mesh
    fragments=[u.load_asset(root+f'/Debris/SM_OilFragment_{i:02}') for i in range(20)]
    assert all(fragments)
    for a in [mesh,*fragments]:
        u.EditorAssetLibrary.set_metadata_tag(a,'OilWindingVersion','UE-CW-1')
        assert u.EditorAssetLibrary.save_loaded_asset(a,False)
    moves={'BP_OilBottle':'','NS_OilDroplets':'VFX','SM_OilDroplet':'VFX','M_OilNiagaraDroplet':'VFX',
           'M_OilDroplet':'VFX','M_OilPlaceholder':'Materials','M_OilTint':'Materials'}
    moved=[]
    for name,folder in moves.items():
        dest=root+('/'+folder if folder else '')+'/'+name
        if not u.EditorAssetLibrary.does_asset_exist(dest):
            asset=u.load_asset(old+'/'+name);assert asset,name
            assert assets.rename_assets([u.AssetRenameData(asset,root+('/'+folder if folder else ''),name)])
            moved.append(dest)
    bp=u.load_asset(root+'/BP_OilBottle');assert bp
    cdo=u.get_default_object(bp.generated_class())
    def assign(a):
        a.modify();a.fragment_meshes=fragments
        a.get_component_by_class(u.ProphecyOilLiquid).set_editor_property('liquid_material',liquid)
        a.set_editor_property('break_impact_speed',250);a.set_editor_property('break_on_hit',True)
        a.set_editor_property('spawn_fragments',True);a.fragment_velocity=120;a.fragment_lifetime=4;a.fragment_fade_duration=1
        b=a.get_editor_property('bottle');b.modify();b.set_static_mesh(mesh);b.set_relative_scale3d(u.Vector(1,1,1))
        b.set_mass_override_in_kg('',.55,True)
        # Remove the placeholder's surface override; source mesh owns glass/cork slots.
        b.set_editor_property('override_materials',[])
    assign(cdo)
    # New placements sit still until thrown; existing test launch settings are preserved.
    cdo.set_editor_property('launch_on_play',False)
    u.BlueprintEditorLibrary.compile_blueprint(bp)
    assert u.EditorAssetLibrary.save_loaded_asset(bp,False)
    rows=[]
    for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if isinstance(a,u.ProphecyOilBottle):
            assign(a)
            # These two authored demonstrations launch; changing the CDO propagated
            # its old inherited true value to false during compilation above.
            a.set_editor_property('launch_on_play',True)
            rows.append({'label':a.get_actor_label(),'launch':a.get_editor_property('launch_on_play'),'scale':str(a.get_actor_scale3d())})
    assert len(rows)==2
    # Save renamed assets so new hard references persist; keep small redirectors for old tools/references.
    for path in u.EditorAssetLibrary.list_assets(root,True,False):
        a=u.load_asset(path)
        if a:assert u.EditorAssetLibrary.save_loaded_asset(a,False)
    assert u.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(),old+'/M_OilTest')
    (out/'installed.json').write_text(json.dumps({'moved':moved,'instances':rows,'fragment_count':len(fragments)},indent=2))
    (out/'install-error.txt').unlink(missing_ok=True)
    success=True
except Exception:
    (out/'install-error.txt').write_text(traceback.format_exc());raise
finally:
    if success and '-ProphecyOilBottleCheck' in u.SystemLibrary.get_command_line():
        runpy.run_path(str(Path(__file__).with_name('TestBottle.py')),run_name='__main__')
    else:u.SystemLibrary.quit_editor()
