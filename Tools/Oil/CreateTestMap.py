"""Run only in a dedicated -ProphecyOilSetup editor; never modifies existing maps."""
import json
from pathlib import Path
import unreal as u

assert '-ProphecyOilSetup' in u.SystemLibrary.get_command_line()
root='/Game/_mygame/Tests/Oil'
assets=u.AssetToolsHelpers.get_asset_tools()
editor=u.get_editor_subsystem(u.EditorActorSubsystem)
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
u.EditorAssetLibrary.make_directory(root)

def material(name,color,roughness,oil=False,terrain=False):
    path=root+'/'+name
    m=u.load_asset(path)
    if m:return m
    m=assets.create_asset(name,root,u.Material,u.MaterialFactoryNew())
    lib=u.MaterialEditingLibrary
    if oil:
        m.set_editor_property('material_domain',u.MaterialDomain.MD_DEFERRED_DECAL)
        m.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
        uv=lib.create_material_expression(m,u.MaterialExpressionTextureCoordinate,-600,200)
        alpha=lib.create_material_expression(m,u.MaterialExpressionScalarParameter,-600,400)
        alpha.set_editor_property('parameter_name','OilAmount');alpha.set_editor_property('default_value',1)
        mask=lib.create_material_expression(m,u.MaterialExpressionCustom,-200,300)
        mask.set_editor_property('code','return saturate((1-length(UV*2-1))/.05)*OilAmount;')
        mask.set_editor_property('output_type',u.CustomMaterialOutputType.CMOT_FLOAT1)
        inputs=[]
        for name in ['UV','OilAmount']:
            i=u.CustomInput();i.set_editor_property('input_name',name);inputs.append(i)
        mask.set_editor_property('inputs',inputs)
        lib.connect_material_expressions(uv,'',mask,'UV');lib.connect_material_expressions(alpha,'',mask,'OilAmount')
        lib.connect_material_property(mask,'',u.MaterialProperty.MP_OPACITY)
    if terrain:
        m.set_editor_property('blend_mode',u.BlendMode.BLEND_MASKED)
        holes=lib.create_material_expression(m,u.MaterialExpressionLandscapeVisibilityMask,-400,400)
        lib.connect_material_property(holes,'',u.MaterialProperty.MP_OPACITY_MASK)
    c=lib.create_material_expression(m,u.MaterialExpressionConstant3Vector,-400,-100)
    c.set_editor_property('constant',u.LinearColor(*color,1));lib.connect_material_property(c,'',u.MaterialProperty.MP_BASE_COLOR)
    r=lib.create_material_expression(m,u.MaterialExpressionConstant,-200,0)
    r.set_editor_property('r',roughness);lib.connect_material_property(r,'',u.MaterialProperty.MP_ROUGHNESS)
    lib.recompile_material(m);u.EditorAssetLibrary.save_loaded_asset(m)
    return m

oil=material('M_OilPlaceholder',(0.018,0.012,0.004),.07,True)
floor=material('M_OilLabFloor',(.5,.55,.6),.6)
terrain_mat=material('M_OilLabLandscape',(.32,.38,.22),.6,terrain=True)
bottle_mat=material('M_OilBottlePlaceholder',(.15,.24,.035),.22)
splash_path=root+'/NS_OilSplashPlaceholder'
splash=u.load_asset(splash_path)
if not splash:
    splash=u.EditorAssetLibrary.duplicate_asset('/Niagara/DefaultAssets/Templates/Systems/RadialBurst',splash_path)
    assert splash,'Niagara template unavailable'
    u.EditorAssetLibrary.save_loaded_asset(splash)
bp_path=root+'/BP_OilBottle'
bp=u.load_asset(bp_path)
if not bp:
    factory=u.BlueprintFactory();factory.set_editor_property('parent_class',u.ProphecyOilBottle)
    bp=assets.create_asset('BP_OilBottle',root,u.Blueprint,factory)
    u.BlueprintEditorLibrary.compile_blueprint(bp)
    defaults=u.get_default_object(bp.generated_class())
    defaults.set_editor_property('oil',u.ProphecyOilSettings(radius=180,slipperiness=1,hold_duration=10,fade_duration=15,decal_material=oil,splash_system=splash))
    defaults.get_editor_property('bottle').set_material(0,bottle_mat)
    u.EditorAssetLibrary.save_loaded_asset(bp)
map_path=root+'/M_OilTest'
if u.EditorAssetLibrary.does_asset_exist(map_path):
    assert not (Path(u.Paths.project_saved_dir())/'Diagnostics/Oil/setup.json').exists(),'Completed test map preserved'
    assert level.load_level(map_path)
    assert not any(a.get_actor_label().startswith('Oil_') for a in editor.get_all_level_actors()),'Partially populated map preserved'
else:assert level.new_level(map_path)
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
setup=editor.spawn_actor_from_class(u.ProphecyJoltFightSetup,u.Vector(0,0,0));setup.set_actor_label('Oil_JoltSetup')
cube=u.load_asset('/Engine/BasicShapes/Cube')
def mesh(label,pos,scale,simulate=False):
    a=editor.spawn_actor_from_class(u.StaticMeshActor,u.Vector(*pos));a.set_actor_label(label);a.set_editor_property('tags',[label])
    c=a.static_mesh_component;c.set_static_mesh(cube);c.set_material(0,floor)
    c.set_mobility(u.ComponentMobility.MOVABLE if simulate else u.ComponentMobility.STATIC)
    a.set_actor_scale3d(u.Vector(*scale));c.set_collision_profile_name('PhysicsActor' if simulate else 'BlockAll')
    if simulate:c.set_simulate_physics(True)
    return a
mesh('Oil_MeshFloor',(-650,0,-20),(12,24,.4))
mesh('Oil_RaisedDeck',(-300,500,120),(5,5,.2))
mesh('Oil_Wall',(-300,900,130),(5,.2,3))
mesh('Slider_Wet',(-900,-400,20),(.3,.3,.3),True)
mesh('Slider_Dry',(-900,100,20),(.3,.3,.3),True)
mesh('Oil_MovingCrate',(-600,600,60),(1.8,1.8,1.2),True)
u.SystemLibrary.execute_console_command(world,'Prophecy.Oil.CreateTerrain')
for a in editor.get_all_level_actors():
    if isinstance(a,u.Landscape):a.set_editor_property('landscape_material',terrain_mat)
for name,pos in [('Mesh',(-1100,-400,180)),('Terrain',(600,-200,180))]:
    a=editor.spawn_actor_from_class(bp.generated_class(),u.Vector(*pos));a.set_actor_label('Oil_Bottle_'+name)
    a.set_editor_property('launch_velocity',u.Vector(200,0,0))
sk=u.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
if sk:
    actor=editor.spawn_actor_from_class(u.SkeletalMeshActor,u.Vector(-650,-400,120),u.Rotator(0,0,80))
    actor.set_actor_label('Oil_LimbTest')
    comp=actor.skeletal_mesh_component;comp.set_skeletal_mesh_asset(sk)
    comp.set_collision_profile_name('PhysicsActor');comp.set_simulate_physics(True)
light=editor.spawn_actor_from_class(u.DirectionalLight,u.Vector(0,0,1000),u.Rotator(-55,-25,0))
light.light_component.set_editor_property('intensity',4)
sky=editor.spawn_actor_from_class(u.SkyLight,u.Vector(0,0,600))
sky.light_component.set_editor_property('intensity',1)
editor.spawn_actor_from_class(u.SkyAtmosphere,u.Vector(0,0,0))
editor.spawn_actor_from_class(u.PlayerStart,u.Vector(-1500,-1000,650),u.Rotator(-20,30,0))
for text,pos in [('MESH / OIL',(-850,-600,50)),('LANDSCAPE / OIL',(650,-500,50)),('MOVABLE RECEIVER',(-650,800,70))]:
    a=editor.spawn_actor_from_class(u.TextRenderActor,u.Vector(*pos),u.Rotator(0,-90,0))
    a.text_render.set_text(text);a.text_render.set_world_size(35)
level.save_current_level()
out=Path(u.Paths.project_saved_dir())/'Diagnostics/Oil';out.mkdir(parents=True,exist_ok=True)
(out/'setup.json').write_text(json.dumps({'map':map_path,'bottle':bp_path,'decal':oil.get_path_name(),'splash':splash.get_path_name()}))
print('OIL_SETUP_COMPLETE',map_path)
