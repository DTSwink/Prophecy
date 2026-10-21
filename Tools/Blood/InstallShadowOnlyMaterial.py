"""Assign a shadow-only material to the user's existing blood mesh renderer."""
import pathlib
import unreal

SYSTEM = '/Game/_mygame/blood2/NS_bloodsplat2'
MATERIAL = '/Game/_mygame/blood2/M_Blood_ShadowOnly'
system = unreal.load_asset(SYSTEM)
renderer = unreal.find_object(None, SYSTEM + '.NS_bloodsplat2:Fountain001_0.NiagaraMeshRendererProperties_0')
assert system and renderer
overrides = renderer.get_editor_property('OverrideMaterials')
assert len(overrides) == 1, 'Expected the existing single material override'
entry = overrides[0]
old_material = entry.get_editor_property('ExplicitMat')
print('Previous override:', old_material)
binding = entry.get_editor_property('UserParamBinding')
print('User binding:', binding)

material = unreal.load_asset(MATERIAL)
assert not material, 'Material already exists; inspect it before reapplying'
with unreal.ScopedEditorTransaction('Blood mesh shadows only'):
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'M_Blood_ShadowOnly', '/Game/_mygame/blood2', unreal.Material, unreal.MaterialFactoryNew())
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
    material.set_editor_property('used_with_niagara_mesh_particles', True)
    lib = unreal.MaterialEditingLibrary
    zero = lib.create_material_expression(material, unreal.MaterialExpressionConstant, -500, 0)
    zero.set_editor_property('r', 0.0)
    one = lib.create_material_expression(material, unreal.MaterialExpressionConstant, -500, 150)
    one.set_editor_property('r', 1.0)
    switch = lib.create_material_expression(material, unreal.MaterialExpressionShadowReplace, -250, 50)
    assert lib.connect_material_expressions(zero, '', switch, 'Default')
    assert lib.connect_material_expressions(one, '', switch, 'Shadow')
    assert lib.connect_material_property(switch, '', unreal.MaterialProperty.MP_OPACITY_MASK)
    lib.recompile_material(material)
    system.modify()
    renderer.modify()
    entry.set_editor_property('ExplicitMat', material)
    overrides[0] = entry
    renderer.set_editor_property('OverrideMaterials', overrides)
    assert renderer.get_editor_property('OverrideMaterials')[0].get_editor_property('ExplicitMat') == material

# Save only assets directly changed for this request; leave map and visual material alone.
assert unreal.EditorAssetLibrary.save_loaded_asset(material)
assert unreal.EditorAssetLibrary.save_loaded_asset(system)
out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/BloodShadows'
for obj, name in [(system, 'after.txt'), (material, 'shadow-material.txt')]:
    t = unreal.AssetExportTask()
    t.object = obj
    t.filename = str(out / name)
    t.exporter = unreal.ObjectExporterT3D()
    t.automated = True
    t.prompt = False
    t.replace_identical = True
    assert unreal.Exporter.run_asset_export_task(t)
print('Installed and saved:', MATERIAL)
print('Play still active:', bool(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()))
