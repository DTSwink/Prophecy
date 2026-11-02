"""User-requested oil revision. Only edits this feature's isolated test assets/map."""
import json, shutil
from pathlib import Path
import unreal as u

assert '-ProphecyOilRefine' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
root='/Game/_mygame/Tests/Oil'
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Revision'
out.mkdir(parents=True,exist_ok=True)
backup=out/'before';backup.mkdir(exist_ok=True)
disk=Path(u.Paths.project_content_dir())/'_mygame/Tests/Oil'
for name in ['M_OilPlaceholder.uasset','M_OilLabFloor.uasset','M_OilTest.umap','BP_OilBottle.uasset']:
    if not (backup/name).exists():shutil.copy2(disk/name,backup/name)
lib=u.MaterialEditingLibrary
assets=u.AssetToolsHelpers.get_asset_tools()

def material(name):
    m=u.load_asset(root+'/'+name) or assets.create_asset(name,root,u.Material,u.MaterialFactoryNew())
    # UE's helper removes from the same array it iterates. Repeat until empty.
    for _ in range(32):
        if lib.get_num_material_expressions(m)==0:break
        lib.delete_all_material_expressions(m)
    assert lib.get_num_material_expressions(m)==0
    return m
def node(m,cls,**props):
    n=lib.create_material_expression(m,cls)
    for k,v in props.items():n.set_editor_property(k,v)
    return n
def scalar(m,name,value):return node(m,u.MaterialExpressionScalarParameter,parameter_name=name,default_value=value)
def color(m,value):return node(m,u.MaterialExpressionConstant3Vector,constant=u.LinearColor(*value,1))
def wire(n,prop):assert lib.connect_material_property(n,'',prop)
def custom(m,code,inputs,kind=u.CustomMaterialOutputType.CMOT_FLOAT1):
    n=node(m,u.MaterialExpressionCustom,code=code,output_type=kind)
    entries=[]
    for name in inputs:
        i=u.CustomInput();i.set_editor_property('input_name',name);entries.append(i)
    n.set_editor_property('inputs',entries)
    for name,source in inputs.items():assert lib.connect_material_expressions(source,'',n,name)
    return n
def save(m):
    lib.layout_material_expressions(m);lib.recompile_material(m)
    assert u.EditorAssetLibrary.save_loaded_asset(m)

oil=material('M_OilPlaceholder')
oil.set_editor_property('material_domain',u.MaterialDomain.MD_DEFERRED_DECAL)
oil.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
uv=node(oil,u.MaterialExpressionTextureCoordinate)
amount=scalar(oil,'OilAmount',1);spread=scalar(oil,'Spread',1);seed=scalar(oil,'ShapeSeed',0)
# A fractional DBuffer edge blends roughness and creates a bright intermediate
# reflection ring. Preserve the former 50% contour, with uniform wet coverage.
mask=custom(oil,'float2 p=(UV*2-1)/max(Spread,0.01); float a=atan2(p.y,p.x); float edge=0.94+0.035*sin(3*a+Seed)+0.025*sin(7*a+2*Seed); return step(0.0175,edge-length(p))*Amount;',
    {'UV':uv,'Amount':amount,'Spread':spread,'Seed':seed})
wire(mask,u.MaterialProperty.MP_OPACITY)
wire(scalar(oil,'OilRoughness',.08),u.MaterialProperty.MP_ROUGHNESS)
wire(scalar(oil,'OilSpecular',.5),u.MaterialProperty.MP_SPECULAR)
# No BaseColor/Normal connection: the DBuffer coating preserves receiver color and detail.
assert lib.get_material_property_input_node(oil,u.MaterialProperty.MP_BASE_COLOR) is None
assert lib.get_material_property_input_node(oil,u.MaterialProperty.MP_NORMAL) is None
save(oil)

drops=material('M_OilDroplet')
drops.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
drops.set_editor_property('translucency_lighting_mode',u.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
drops.set_editor_property('used_with_instanced_static_meshes',True)
wire(color(drops,(.82,.58,.10)),u.MaterialProperty.MP_BASE_COLOR)
wire(scalar(drops,'DropletRoughness',.06),u.MaterialProperty.MP_ROUGHNESS)
wire(scalar(drops,'DropletSpecular',.65),u.MaterialProperty.MP_SPECULAR)
fresnel=node(drops,u.MaterialExpressionFresnel,exponent=3.,base_reflect_fraction=.18)
opacity=custom(drops,'return 0.22+F*0.5;',{'F':fresnel})
wire(opacity,u.MaterialProperty.MP_OPACITY);save(drops)

floor=material('M_OilLabFloor')
pos=node(floor,u.MaterialExpressionWorldPosition)
tiles=custom(floor,'float2 p=P.xy/100; float2 f=frac(p); float tile=fmod(floor(p.x)+floor(p.y),2); float grout=step(0.018,min(min(f.x,1-f.x),min(f.y,1-f.y))); return lerp(float3(.19,.20,.21),lerp(float3(.37,.40,.43),float3(.46,.48,.5),abs(tile)),grout);',
             {'P':pos},u.CustomMaterialOutputType.CMOT_FLOAT3)
wire(tiles,u.MaterialProperty.MP_BASE_COLOR);wire(scalar(floor,'DryRoughness',.72),u.MaterialProperty.MP_ROUGHNESS);save(floor)

settings=u.ProphecyOilSettings(radius=150,slipperiness=1,hold_duration=4,fade_duration=4,
    decal_material=oil,droplet_material=drops,droplet_count=24,splash_system=None)
bp=u.load_asset(root+'/BP_OilBottle');defaults=u.get_default_object(bp.generated_class())
defaults.set_editor_property('oil',settings);u.BlueprintEditorLibrary.compile_blueprint(bp)
assert u.EditorAssetLibrary.save_loaded_asset(bp)
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
cube=u.load_asset('/Engine/MapTemplates/Sky/DaylightAmbientCubemap')
for actor in actors.get_all_level_actors():
    if isinstance(actor,u.ProphecyOilBottle):actor.set_editor_property('oil',settings)
    if isinstance(actor,u.DirectionalLight):
        actor.light_component.set_editor_property('atmosphere_sun_light',True)
        actor.light_component.set_editor_property('intensity',4.)
        actor.set_actor_rotation(u.Rotator(-30,-130,0),False)
        actor.light_component.set_editor_property('light_source_angle',3.)
    if isinstance(actor,u.SkyLight):
        actor.light_component.set_editor_property('source_type',u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
        actor.light_component.set_cubemap(cube);actor.light_component.set_intensity(2.)
    if isinstance(actor,u.TextRenderActor):actors.destroy_actor(actor)
if not any(a.get_actor_label()=='Oil_Reflection' for a in actors.get_all_level_actors()):
    reflection=actors.spawn_actor_from_class(u.SphereReflectionCapture,u.Vector(-300,-200,100))
    reflection.set_actor_label('Oil_Reflection')
    comp=reflection.get_component_by_class(u.SphereReflectionCaptureComponent)
    comp.set_editor_property('influence_radius',4000.)
    comp.set_editor_property('reflection_source_type',u.ReflectionSourceType.SPECIFIED_CUBEMAP)
    comp.set_editor_property('cubemap',cube)
for label,position,target in [('Oil_SoftboxMesh',(-720,-100,250),(-980,-400,0)),('Oil_SoftboxTerrain',(980,100,260),(710,-210,0))]:
    light=next((a for a in actors.get_all_level_actors() if a.get_actor_label()==label),None)
    if light is None:light=actors.spawn_actor_from_class(u.RectLight,u.Vector(*position))
    light.set_actor_label(label)
    light.set_actor_rotation(u.MathLibrary.find_look_at_rotation(u.Vector(*position),u.Vector(*target)),False)
    c=light.get_component_by_class(u.RectLightComponent)
    c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_editor_property('intensity',600.)
    c.set_editor_property('attenuation_radius',900.)
    c.set_editor_property('source_width',180.)
    c.set_editor_property('source_height',45.)
    c.set_editor_property('cast_shadows',False)
u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
(out/'appearance.json').write_text(json.dumps({'hold':4,'fade':4,'drops':24,'decal':'roughness/specular only','base_color_connected':False,'map':root+'/M_OilTest'}))
print('OIL_APPEARANCE_REFINED')
if '-ProphecyOilVideo' in u.SystemLibrary.get_command_line():
    exec((Path(u.Paths.project_dir())/'Tools/Oil/RecordVideo.py').read_text(),{})
