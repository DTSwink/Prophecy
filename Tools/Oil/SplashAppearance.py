"""Fuller oil splash and faint tint; isolated feature assets only."""
import hashlib, json, shutil
from pathlib import Path
import unreal as u

assert '-ProphecyOilSplash' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
root='/Game/_mygame/Tests/Oil';lib=u.MaterialEditingLibrary
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Splash'
out.mkdir(parents=True,exist_ok=True)
backup=out/'before';backup.mkdir(exist_ok=True)
disk=Path(u.Paths.project_content_dir()).resolve()/'_mygame/Tests/Oil'
for name in ['M_OilDroplet.uasset','BP_OilBottle.uasset','M_OilTest.umap']:
    if not (backup/name).exists():shutil.copy2(disk/name,backup/name)

def node(m,cls,**props):
    n=lib.create_material_expression(m,cls)
    for k,v in props.items():n.set_editor_property(k,v)
    return n
def scalar(m,name,value):return node(m,u.MaterialExpressionScalarParameter,parameter_name=name,default_value=value)
def custom(m,code,inputs):
    n=node(m,u.MaterialExpressionCustom,code=code,output_type=u.CustomMaterialOutputType.CMOT_FLOAT1)
    entries=[]
    for name in inputs:
        i=u.CustomInput();i.set_editor_property('input_name',name);entries.append(i)
    n.set_editor_property('inputs',entries)
    for name,(source,pin) in inputs.items():assert lib.connect_material_expressions(source,pin,n,name)
    return n
def save(m):
    lib.layout_material_expressions(m);lib.recompile_material(m)
    u.SystemLibrary.execute_console_command(ed.get_editor_world(),'Editor.AsyncAssetCompilationFinishAll')
    assert u.EditorAssetLibrary.save_loaded_asset(m)

drops=u.load_asset(root+'/M_OilDroplet')
color=lib.get_material_property_input_node(drops,u.MaterialProperty.MP_BASE_COLOR)
assert isinstance(color,u.MaterialExpressionConstant3Vector)
color.set_editor_property('constant',u.LinearColor(.90,.73,.20,1))
drops.set_editor_property('two_sided',True)
old=lib.get_material_property_input_node(drops,u.MaterialProperty.MP_OPACITY)
if isinstance(old,u.MaterialExpressionCustom) and old.get_editor_property('code')=='return 0.22+F*0.5;':
    vertex=node(drops,u.MaterialExpressionVertexColor)
    multiply=custom(drops,'return O*A;',{'O':(old,''),'A':(vertex,'A')})
    assert lib.connect_material_property(multiply,'',u.MaterialProperty.MP_OPACITY)
root_opacity=lib.get_material_property_input_node(drops,u.MaterialProperty.MP_OPACITY)
for source in lib.get_inputs_for_material_expression(drops,root_opacity):
    if isinstance(source,u.MaterialExpressionCustom):source.set_editor_property('code','return 0.10+F*0.24;')
# A small warm fill keeps overlapping transparent surfaces readable under the
# lab's dark environment; the lit specular response still supplies highlights.
fill=lib.get_material_property_input_node(drops,u.MaterialProperty.MP_EMISSIVE_COLOR)
if fill is None:fill=node(drops,u.MaterialExpressionConstant3Vector)
assert isinstance(fill,u.MaterialExpressionConstant3Vector)
fill.set_editor_property('constant',u.LinearColor(2.0,1.65,.70,1))
assert lib.connect_material_property(fill,'',u.MaterialProperty.MP_EMISSIVE_COLOR)
save(drops)

tint=u.load_asset(root+'/M_OilTint')
if tint is None:tint=u.AssetToolsHelpers.get_asset_tools().create_asset('M_OilTint',root,u.Material,u.MaterialFactoryNew())
for _ in range(32):
    if lib.get_num_material_expressions(tint)==0:break
    lib.delete_all_material_expressions(tint)
assert lib.get_num_material_expressions(tint)==0
tint.set_editor_property('material_domain',u.MaterialDomain.MD_DEFERRED_DECAL)
tint.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
coating=u.load_asset(root+'/M_OilPlaceholder')
mask_code=lib.get_material_property_input_node(coating,u.MaterialProperty.MP_OPACITY).get_editor_property('code')
assert 'step(0.0175' in mask_code
mask=custom(tint,mask_code.replace('*Amount;','*Amount*Strength;'),{
    'UV':(node(tint,u.MaterialExpressionTextureCoordinate),''),
    'Amount':(scalar(tint,'OilAmount',1),''),'Spread':(scalar(tint,'Spread',1),''),
    'Seed':(scalar(tint,'ShapeSeed',0),''),'Strength':(scalar(tint,'TintStrength',.035),'')})
tint_color=node(tint,u.MaterialExpressionVectorParameter,parameter_name='OilTint',default_value=u.LinearColor(.85,.68,.18,1))
assert lib.connect_material_property(tint_color,'',u.MaterialProperty.MP_BASE_COLOR)
assert lib.connect_material_property(mask,'',u.MaterialProperty.MP_OPACITY)
assert lib.get_material_property_input_node(tint,u.MaterialProperty.MP_ROUGHNESS) is None
save(tint)

def splash_settings(previous):
    names=['radius','slipperiness','hold_duration','fade_duration','decal_material','splash_system','droplet_material']
    return u.ProphecyOilSettings(**{name:previous.get_editor_property(name) for name in names},droplet_count=56,tint_material=tint)
bp=u.load_asset(root+'/BP_OilBottle');u.BlueprintEditorLibrary.compile_blueprint(bp)
defaults=u.get_default_object(bp.generated_class());defaults.modify()
defaults.set_editor_property('oil',splash_settings(defaults.get_editor_property('oil')))
assert defaults.get_editor_property('oil').get_editor_property('tint_material')==tint
assert u.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
    if isinstance(actor,u.ProphecyOilBottle):
        actor.modify()
        actor.set_editor_property('oil',splash_settings(actor.get_editor_property('oil')))
        assert actor.get_editor_property('oil').get_editor_property('tint_material')==tint
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
(out/'appearance.json').write_text(json.dumps({'drops':56,'tint_strength':.035,'tint_rgb':[.85,.68,.18],
    'sheet_max_ticks':20,'saved':['M_OilDroplet','M_OilTint','BP_OilBottle','M_OilTest'],
    'coating_sha256':hashlib.sha256((disk/'M_OilPlaceholder.uasset').read_bytes()).hexdigest()},indent=2))
print('OIL_SPLASH_APPEARANCE_READY')
if '-ProphecyOilVideo' in u.SystemLibrary.get_command_line():
    exec((Path(u.Paths.project_dir())/'Tools/Oil/RecordVideo.py').read_text(),{})
