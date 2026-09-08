"""Head-only UV-anchored collar AO fade in the existing isolated Boss shader.

Neutral at the collar, original AO and bent normals past the fade band.
No geometry, source textures, or shared MetaHuman master edits.
"""
from pathlib import Path
import unreal

lib = unreal.MaterialEditingLibrary
root = '/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair'
function = unreal.load_asset(root + '/MF_skin_bentNormalsAO_BossAO')
master = unreal.load_asset(root + '/M_skin_unified_baked_BossAO')
nodes = {o.get_name(): o for o in unreal.ObjectIterator(unreal.MaterialExpression)
         if o.get_path_name().startswith(function.get_path_name() + ':')}
assert not any(isinstance(o, unreal.MaterialExpressionStaticBoolParameter)
               and str(o.get_editor_property('parameter_name')) == 'Use Boss Neck AO Fade'
               for o in nodes.values()), 'Neck fade already exists'

task = unreal.AssetImportTask()
task.filename = str(Path(unreal.Paths.project_saved_dir()).resolve() / 'BossShading/20260908/NeckFade/T_Boss_NeckDistance.png')
task.destination_path = root
task.destination_name = 'T_Boss_NeckDistance'
task.automated = True
task.replace_existing = False
task.save = False
assert not unreal.EditorAssetLibrary.does_asset_exist(root + '/T_Boss_NeckDistance')
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
texture = unreal.load_asset(root + '/T_Boss_NeckDistance')
assert texture
texture.set_editor_property('srgb', False)
texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_GRAYSCALE)
texture.set_editor_property('address_x', unreal.TextureAddress.TA_CLAMP)
texture.set_editor_property('address_y', unreal.TextureAddress.TA_CLAMP)

created = []
def make(kind, **properties):
    node = lib.create_material_expression_in_function(function, kind)
    created.append(node)
    for name, value in properties.items():
        node.set_editor_property(name, value)
    return node

def link(source, source_pin, destination, destination_pin):
    assert lib.connect_material_expressions(source, source_pin, destination, destination_pin)

enabled = make(unreal.MaterialExpressionStaticBoolParameter,
               parameter_name='Use Boss Neck AO Fade', group='Boss Neck AO', default_value=False)
mask = make(unreal.MaterialExpressionTextureSampleParameter2D,
            parameter_name='Boss Neck Distance Mask', group='Boss Neck AO', texture=texture,
            sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
centimeters = make(unreal.MaterialExpressionMultiply, const_b=10.)
link(mask, 'R', centimeters, 'A')
border = make(unreal.MaterialExpressionScalarParameter,
              parameter_name='Neck AO Neutral Border Cm', group='Boss Neck AO', default_value=.2,
              slider_min=0., slider_max=1.)
width = make(unreal.MaterialExpressionScalarParameter,
             parameter_name='Neck AO Fade Width Cm', group='Boss Neck AO', default_value=5.,
             slider_min=.1, slider_max=9.)
distance = make(unreal.MaterialExpressionSubtract)
link(centimeters, '', distance, 'A')
link(border, '', distance, 'B')
safe_width = make(unreal.MaterialExpressionMax, const_b=.01)
link(width, '', safe_width, 'A')
ratio = make(unreal.MaterialExpressionDivide)
link(distance, '', ratio, 'A')
link(safe_width, '', ratio, 'B')
alpha = make(unreal.MaterialExpressionSaturate)
link(ratio, '', alpha, '')

neutral_scalar = make(unreal.MaterialExpressionConstant, r=1.)
neutral_normal = nodes['MaterialExpressionConstant3Vector_0']

def fade(source, neutral, destination, pin):
    blend = make(unreal.MaterialExpressionLinearInterpolate)
    link(neutral, '', blend, 'A')
    link(source, '', blend, 'B')
    link(alpha, '', blend, 'Alpha')
    gate = make(unreal.MaterialExpressionStaticSwitch)
    link(blend, '', gate, 'True')
    link(source, '', gate, 'False')
    link(enabled, '', gate, 'Value')
    link(gate, '', destination, pin)

fade(nodes['MaterialExpressionStaticSwitchParameter_0'], neutral_scalar,
     nodes['MaterialExpressionSetMaterialAttributes_0'], 'AmbientOcclusion')
fade(nodes['MaterialExpressionStaticSwitch_0'], neutral_normal,
     nodes['MaterialExpressionFunctionOutput_1'], '')
fade(nodes['MaterialExpressionStaticSwitch_1'], neutral_scalar,
     nodes['MaterialExpressionFunctionOutput_2'], '')
lib.update_material_function(function)
lib.recompile_material(master)

# Only the existing isolated test head enables the new branch initially.
test_head = repair['test_materials'][7]
lib.set_material_instance_static_switch_parameter_value(test_head, 'Use Boss Neck AO Fade', True)
assert lib.get_material_instance_static_switch_parameter_value(test_head, 'Use Boss Neck AO Fade')
lib.update_material_instance(test_head)
print('BOSS_NECK_FADE_TEST_READY', texture.get_path_name(), 'border_cm=0.2 width_cm=5')
