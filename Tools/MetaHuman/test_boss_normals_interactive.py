"""User-observed normal isolation on the open skeletal-mesh preview only.

All test materials live under /Engine/Transient. Never changes or saves the
mesh's material slots, original material instances, maps, or textures.
Call apply('baseline'), apply('no_lod'), or apply('vertex_only'); stop() restores.
"""
import unreal

lib=unreal.MaterialEditingLibrary
asset=unreal.load_asset('/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted')
components=[c for c in unreal.ObjectIterator(unreal.SkeletalMeshComponent)
            if c.get_skeletal_mesh_asset()==asset and c.get_world()
            and c.get_world().get_path_name().startswith('/Engine/Transient.')
            and c.get_owner() and c.get_owner().get_class().get_name()=='AnimationEditorPreviewActor']
assert len(components)==1, 'Expected one open fitted-mesh preview; do not change level actors'
component=components[0]
original_overrides=list(component.get_editor_property('override_materials'))
originals={i:component.get_material(i) for i in (0,7)}
materials=[]
state={'mode':'baseline'}

def stop():
    component.set_editor_property('override_materials',original_overrides)
    state['mode']='baseline'
    print('NORMAL_TEST_RESTORED')

def apply(mode):
    assert mode in ('baseline','no_lod','vertex_only','no_specular')
    stop()
    if mode=='baseline':return
    for index,parent in originals.items():
        instance=unreal.MaterialInstanceConstant()
        materials.append(instance)
        lib.set_material_instance_parent(instance,parent)
        if index==7:
            lib.set_material_instance_static_switch_parameter_value(instance,'Normal LOD Baked',False)
        if mode in ('vertex_only','no_specular'):
            # Flatten the final global normal contribution and remove micro detail;
            # also neutralize both baked texture inputs to independently cover them.
            lib.set_material_instance_scalar_parameter_value(instance,'Normal Global Strength Post-Bake',0.)
            lib.set_material_instance_scalar_parameter_value(instance,'Micro Skin Normal Strength',0.)
            flat=unreal.load_asset('/Game/MetaHumans/Common/Lookdev_UHM/Common/Textures/Placeholders/T_Flat_N')
            flat_vt=unreal.load_asset('/Game/MetaHumans/Common/Lookdev_UHM/Common/Textures/Placeholders/T_Flat_N_VT')
            for name,texture in [('Normal Baked VT',flat_vt),('Normal Baked',flat),('Normal LOD Baked',flat)]:
                lib.set_material_instance_texture_parameter_value(instance,name,texture)
        if mode=='no_specular':
            lib.set_material_instance_scalar_parameter_value(instance,'Specular Global Multiply Post-Bake',0.)
            lib.set_material_instance_scalar_parameter_value(instance,'Specular Global Offset Post-Bake',0.)
            lib.set_material_instance_scalar_parameter_value(instance,'Specular Off (no PT)',1.)
        lib.update_material_instance(instance)
        component.set_material(index,instance)
        assert component.get_material(index)==instance
        print('TEST_MATERIAL',index,instance.get_path_name(),
              'LOD',lib.get_material_instance_static_switch_parameter_value(instance,'Normal LOD Baked'),
              'Strength',lib.get_material_instance_scalar_parameter_value(instance,'Normal Global Strength Post-Bake'))
    state['mode']=mode
    print('NORMAL_TEST_MODE',mode,'PREVIEW',component.get_path_name(),'ASSETS_SAVED',False)

if not globals().get('definitions_only',False):
    apply('vertex_only')
