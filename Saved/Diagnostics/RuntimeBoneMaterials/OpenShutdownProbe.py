import unreal, json, pathlib

editors = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
material = unreal.load_asset('/Engine/EngineMaterials/DefaultPhysicalMaterial')
assert isinstance(material, unreal.PhysicalMaterial)
assert editors.open_editor_for_assets([material])
result = {'opened_physical_material': material.get_path_name(), 'open_editor_returned': True,
          'dirty_content': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
          'dirty_maps': [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RuntimeBoneMaterials/shutdown_probe.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
assert not result['dirty_content'] and not result['dirty_maps']
