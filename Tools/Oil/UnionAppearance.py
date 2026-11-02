"""Replace independent splat opacity with shared union coverage; isolated assets only."""
import json, shutil
from pathlib import Path
import unreal as u
assert '-ProphecyOilUnion' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
root='/Game/_mygame/Tests/Oil';lib=u.MaterialEditingLibrary
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Union'
backup=out/'before';backup.mkdir(parents=True,exist_ok=True)
disk=Path(u.Paths.project_content_dir()).resolve()/'_mygame/Tests/Oil'
def node(m,cls,**props):
    n=lib.create_material_expression(m,cls)
    for k,v in props.items():n.set_editor_property(k,v)
    return n
def scalar(m,name,value):return node(m,u.MaterialExpressionScalarParameter,parameter_name=name,default_value=value)
def custom(m,code,inputs,kind=u.CustomMaterialOutputType.CMOT_FLOAT1):
    n=node(m,u.MaterialExpressionCustom,code=code,output_type=kind)
    entries=[]
    for name in inputs:
        i=u.CustomInput();i.set_editor_property('input_name',name);entries.append(i)
    n.set_editor_property('inputs',entries)
    for name,(source,pin) in inputs.items():assert lib.connect_material_expressions(source,pin,n,name)
    return n
for name in ['M_OilPlaceholder','M_OilTint']:
    if not (backup/(name+'.uasset')).exists():shutil.copy2(disk/(name+'.uasset'),backup/(name+'.uasset'))
    m=u.load_asset(root+'/'+name)
    old=lib.get_material_property_input_node(m,u.MaterialProperty.MP_OPACITY)
    if isinstance(old,u.MaterialExpressionCustom) and 'step(0.5,Coverage)' in old.get_editor_property('code'):continue
    # Keep the existing color/specular/roughness graph and all authored tuning.
    amount=scalar(m,'OilAmount',1)
    uv=custom(m,'return UV.yx;',{'UV':(node(m,u.MaterialExpressionTextureCoordinate),'')},u.CustomMaterialOutputType.CMOT_FLOAT2)
    default_texture=u.load_asset('/Engine/EngineResources/WhiteSquareTexture');assert default_texture
    sampler=u.MaterialSamplerType.SAMPLERTYPE_COLOR if default_texture.get_editor_property('srgb') else u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR
    tex=node(m,u.MaterialExpressionTextureSampleParameter2D,parameter_name='OilCoverage',texture=default_texture,sampler_type=sampler)
    assert lib.connect_material_expressions(uv,'',tex,'UVs')
    inputs={'Coverage':(tex,'R'),'Amount':(amount,'')}
    code='return step(0.5,Coverage)*Amount;'
    if name=='M_OilTint':
        inputs['Strength']=(scalar(m,'TintStrength',.035),'');code='return step(0.5,Coverage)*Amount*Strength;'
    opacity=custom(m,code,inputs)
    assert lib.connect_material_property(opacity,'',u.MaterialProperty.MP_OPACITY)
    lib.layout_material_expressions(m);lib.recompile_material(m)
    u.SystemLibrary.execute_console_command(ed.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
    assert u.EditorAssetLibrary.save_loaded_asset(m)
(out/'appearance.json').write_text(json.dumps({'saved':['M_OilPlaceholder','M_OilTint'],
    'coverage':'Binary union mask; one tint/gloss application per connected puddle',
    'tint_strength':.035,'uv':'Decal Z,Y swapped to coverage U=local Y,V=local Z'},indent=2))
print('OIL_UNION_APPEARANCE_READY')
if '-ProphecyOilVideo' in u.SystemLibrary.get_command_line():
    exec((Path(u.Paths.project_dir())/'Tools/Oil/RecordVideo.py').read_text(),{})
