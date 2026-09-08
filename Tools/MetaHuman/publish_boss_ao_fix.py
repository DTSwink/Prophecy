"""Publish only the validated Boss material ancestry, not the dirty mesh/map."""
import json
import unreal

copies = repair['copies']
leaves = [repair['source_materials'][i] for i in (0, 7)]
leaf_keys = {m.get_path_name() for m in leaves}
report = {'changed_materials': [], 'saved_support_assets': [],
          'mesh_saved': False, 'shared_function_modified': False,
          'correction': {'before': [.5, .5, 1.], 'after': [0., 0., 1.]}}

def parameters(material):
    result = {}
    for name in ('scalar_parameter_values', 'vector_parameter_values', 'texture_parameter_values'):
        values = []
        for entry in material.get_editor_property(name):
            info = entry.get_editor_property('parameter_info')
            value = entry.get_editor_property('parameter_value')
            if isinstance(value, unreal.Object):
                value = value.get_path_name()
            elif isinstance(value, unreal.LinearColor):
                value = (value.r, value.g, value.b, value.a)
            values.append((str(info.name), str(info.association), info.index, value))
        result[name] = values
    return result

for key, asset in copies.items():
    if key not in leaf_keys:
        assert unreal.EditorAssetLibrary.save_loaded_asset(asset, False)
        report['saved_support_assets'].append(asset.get_path_name())

for material in leaves:
    old_parent = material.get_editor_property('parent')
    new_parent = copies[old_parent.get_path_name()]
    parameters_before = parameters(material)
    unreal.MaterialEditingLibrary.set_material_instance_parent(material, new_parent)
    unreal.MaterialEditingLibrary.update_material_instance(material)
    assert parameters_before == parameters(material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(material, False)
    report['changed_materials'].append({'material': material.get_path_name(),
                                      'old_parent': old_parent.get_path_name(),
                                      'new_parent': new_parent.get_path_name()})

(context['OUT'] / 'ao_fix_publication.json').write_text(json.dumps(report, indent=2))
print('BOSS_AO_PUBLISHED', json.dumps(report))
