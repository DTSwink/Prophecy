"""Prepare the lab's native heterogeneous-volume material; engine assets are read-only.

Executed by prepare_materials.py in Unreal's existing preparation commandlet.
Density is a real 3D field sampled by UE's volume renderer. No surface mesh,
screen-space raymarch, fog sheet, or baked smoke image is used.
"""
import pathlib
import unreal


def prepare_volume_material():
    assert pathlib.Path(unreal.Paths.get_project_file_path()).stem == 'MainMenuSceneLab'
    lib = unreal.MaterialEditingLibrary
    root, name = '/Game/MenuScene', 'M_VolumetricSmoke'
    material = unreal.load_asset(root + '/' + name)
    if not material:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, root, unreal.Material, unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(material)
    material.set_editor_property('material_domain', unreal.MaterialDomain.MD_VOLUME)
    material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ADDITIVE)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    lib.set_material_usage(material, unreal.MaterialUsage.MATUSAGE_HETEROGENEOUS_VOLUMES)

    def expr(cls, **props):
        result = lib.create_material_expression(material, cls)
        for key, value in props.items():
            result.set_editor_property(key, value)
        return result

    def scalar(parameter, value):
        return expr(unreal.MaterialExpressionScalarParameter,
                    parameter_name=parameter, default_value=value)

    def vector(parameter, value):
        return expr(unreal.MaterialExpressionVectorParameter,
                    parameter_name=parameter, default_value=unreal.LinearColor(*value, 0))

    # Epic's authored, tileable volume texture provides actual xyz structure.
    noise = unreal.load_asset('/Engine/EngineSky/VolumetricClouds/VT_PerlinWorley_Balanced')
    if not isinstance(noise, unreal.VolumeTexture):
        raise RuntimeError('Expected installed Epic VolumeTexture VT_PerlinWorley_Balanced')
    texture = expr(unreal.MaterialExpressionTextureObjectParameter,
                   parameter_name='DensityNoise', texture=noise,
                   sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    inputs = {
        'P': expr(unreal.MaterialExpressionWorldPosition),
        'Noise': texture,
        'Center': vector('VolumeCenter', (850, 140, 500)),
        'Extent': vector('VolumeExtent', (650, 1350, 350)),
        'Density': scalar('SmokeDensity', .0006),
        'Softness': scalar('SmokeSoftness', .6),
        'Clock': scalar('SceneTime', 0),
    }
    pins = []
    for key in inputs:
        pin = unreal.CustomInput()
        pin.set_editor_property('input_name', key)
        pins.append(pin)
    density = expr(unreal.MaterialExpressionCustom,
                   output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3,
                   inputs=pins, code=r'''
float3 q = (P - Center.xyz) / max(Extent.xyz, 1.0);
float soft = saturate(Softness);
// A broad, smooth boundary in all three dimensions, with no flat sheet edge.
float3 edge = 1.0 - smoothstep(float3(.36,.5,.24),float3(1,1,1),abs(q));
float envelope = edge.x * edge.y * edge.z;
float3 drift = Clock * float3(.024,.006,-.003);
float3 uv = P / float3(700,1000,480) + drift;
float broad = Texture3DSampleLevel(Noise,NoiseSampler,frac(uv),0).r;
float detail = Texture3DSampleLevel(Noise,NoiseSampler,frac(uv*2.17+float3(.23,.57,.13)-drift*.3),0).r;
float fine = Texture3DSampleLevel(Noise,NoiseSampler,frac(uv*5.03+float3(.61,.19,.77)),0).r;
float field = .67*broad + .25*detail + .08*fine;
// At high softness the field becomes a continuous mist with gentle variation;
// low softness exposes the same genuinely volumetric rolling density structure.
float billow = smoothstep(lerp(.34,.16,soft),lerp(.65,.78,soft),field);
float body = lerp(billow,.18+.68*billow,soft);
float extinction = max(0,Density) * envelope * body;
return extinction.xxx;
''')
    for key, expression in inputs.items():
        lib.connect_material_expressions(expression, '', density, key)

    # UE's legacy Volume-domain path uses SubsurfaceColor as extinction and
    # BaseColor as single-scattering albedo, not the surface Opacity input.
    lib.connect_material_property(density, '', unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    albedo = expr(unreal.MaterialExpressionConstant3Vector,
                  constant=unreal.LinearColor(.72, .76, .82, 1))
    lib.connect_material_property(albedo, '', unreal.MaterialProperty.MP_BASE_COLOR)
    emission = expr(unreal.MaterialExpressionConstant3Vector,
                    constant=unreal.LinearColor(0, 0, 0, 1))
    lib.connect_material_property(emission, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(material)
    assert unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False), 'Could not save volume material; close the scene preview first'
    unreal.log('Prepared native heterogeneous smoke material: ' + material.get_path_name())
    return material


prepare_volume_material()
