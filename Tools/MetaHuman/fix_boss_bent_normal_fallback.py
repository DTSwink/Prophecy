"""Isolated material-chain test of Epic's neutral bent-normal correction.

Copies only the Boss skin instance ancestry, master, and faulty function.
Does not change the source assets, keeper mesh, or save unrelated packages.
"""
import unreal

ROOT = '/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair'
SOURCE_FUNCTION = '/Game/MetaHumans/Common/Lookdev_UHM/Skin/Material_Functions/MF_skin_bentNormalsAO'
source_function = unreal.load_asset(SOURCE_FUNCTION)
source_materials = [m.material_interface for m in context['asset'].materials]
copies = {}

def duplicate(source):
    key = source.get_path_name()
    if key in copies:
        return copies[key]
    destination = ROOT + '/' + source.get_name() + '_BossAO'
    assert not unreal.EditorAssetLibrary.does_asset_exist(destination), destination
    result = unreal.EditorAssetLibrary.duplicate_asset(key, destination)
    assert result
    copies[key] = result
    return result

function = duplicate(source_function)
constants = [o for o in unreal.ObjectIterator(unreal.MaterialExpressionConstant3Vector)
             if o.get_path_name().startswith(function.get_path_name() + ':')]
assert len(constants) == 1
old = constants[0].get_editor_property('constant')
assert (old.r, old.g, old.b) == (.5, .5, 1.)
constants[0].set_editor_property('constant', unreal.LinearColor(r=0., g=0., b=1., a=old.a))
unreal.MaterialEditingLibrary.update_material_function(function)

def clone_chain(source):
    if source.get_path_name() in copies:
        return copies[source.get_path_name()]
    result = duplicate(source)
    if isinstance(source, unreal.MaterialInstanceConstant):
        parent = clone_chain(source.get_editor_property('parent'))
        unreal.MaterialEditingLibrary.set_material_instance_parent(result, parent)
        unreal.MaterialEditingLibrary.update_material_instance(result)
    else:
        assert isinstance(result, unreal.Material)
        calls = [o for o in unreal.ObjectIterator(unreal.MaterialExpressionMaterialFunctionCall)
                 if o.get_path_name().startswith(result.get_path_name() + ':')
                 and o.get_editor_property('material_function') == source_function]
        assert len(calls) == 1
        calls[0].set_editor_property('material_function', function)
        unreal.MaterialEditingLibrary.recompile_material(result)
    return result

test_materials = list(source_materials)
for index in (0, 7):
    test_materials[index] = clone_chain(source_materials[index])

print('BOSS_AO_ISOLATED_TEST_READY', {k: v.get_path_name() for k, v in copies.items()})
