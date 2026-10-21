"""Add seeded edge variation without changing the map or unrelated graphs."""
import pathlib,shutil,sys,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user Play'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordBloodDepth'
bp=unreal.load_asset('/Game/_mygame/sword/A_Sword')
def export(name):
    t=unreal.AssetExportTask();t.object=bp;t.filename=str(out/name);t.exporter=unreal.ObjectExporterT3D()
    t.automated=True;t.prompt=False;t.replace_identical=True
    assert unreal.Exporter.run_asset_export_task(t)
if '--material' in sys.argv:
    path='/Game/Prophecy/BloodTexturePainting/Generated/_mygame_sword_geometry_M_Sword_BloodPaint'
    m=unreal.load_asset(path);lib=unreal.MaterialEditingLibrary
    source=pathlib.Path(unreal.Paths.project_content_dir())/(path.removeprefix('/Game/')+'.uasset')
    backup=out/'paint-material.before-seed.uasset'
    if not backup.exists():shutil.copy2(source,backup)
    nodes=[n for n in unreal.ObjectIterator(unreal.MaterialExpressionCustom) if n.get_outer()==m and n.get_editor_property('description')=='Additive blade-depth coverage']
    assert len(nodes)==1
    mask=nodes[0]
    inputs=list(mask.get_editor_property('inputs'))
    names=[str(x.get_editor_property('input_name')) for x in inputs]
    for name in ['Variation','LateralScale']:
        if name not in names:
            item=unreal.CustomInput();item.set_editor_property('input_name',name);inputs.append(item)
    mask.set_editor_property('inputs',inputs)
    for parameter,name,default,y in [('BladeBloodVariation','Variation',.5,1800),('BladeLateralScale','LateralScale',1.,2000)]:
        candidates=[n for n in unreal.ObjectIterator(unreal.MaterialExpressionScalarParameter) if n.get_outer()==m and str(n.get_editor_property('parameter_name'))==parameter]
        assert len(candidates)<=1
        n=candidates[0] if candidates else lib.create_material_expression(m,unreal.MaterialExpressionScalarParameter,-1800,y)
        n.set_editor_property('parameter_name',parameter);n.set_editor_property('default_value',default);n.set_editor_property('group','Blade Blood')
        assert lib.connect_material_expressions(n,'',mask,name)
    shader=pathlib.Path(unreal.Paths.project_dir())/'Tools/Blood/SwordDepthEdge.ush'
    mask.set_editor_property('code',shader.read_text())
    lib.recompile_material(m)
    assert unreal.EditorAssetLibrary.save_loaded_asset(m,only_if_is_dirty=False)
    print('Seeded material edge saved; existing paint-mask union retained')
else:
    backup=out/'A_Sword.before-seed.uasset'
    if not backup.exists():shutil.copy2(pathlib.Path(unreal.Paths.project_content_dir())/'_mygame/sword/A_Sword.uasset',backup)
    if not (out/'before-seed.txt').exists():export('before-seed.txt')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Blood.SeedSwordDepth')
    export('after-seed.txt')
    print('Seed pin installed; left unsaved for graph and compile checks')
