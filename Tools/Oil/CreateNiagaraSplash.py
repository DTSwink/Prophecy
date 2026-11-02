"""Build the editable cosmetic oil spray in an owned converter-enabled editor."""
import json, sys, traceback, shutil, runpy
from pathlib import Path
import unreal as u

assert '-ProphecyOilNiagaraSetup' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert not ed.get_game_world() and 'M_OilTest' in ed.get_editor_world().get_path_name()
sys.path.insert(0,str(Path(u.Paths.engine_plugins_dir())/'FX/CascadeToNiagaraConverter/Content/Python'))
import Paths as P
fx=u.FXConverterUtilitiesLibrary
root='/Game/_mygame/Tests/Oil'
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/NiagaraFlower'
out.mkdir(parents=True,exist_ok=True)
assets=u.AssetToolsHelpers.get_asset_tools(); lib=u.MaterialEditingLibrary
ctx=None
def arg(path):return u.CreateScriptContextArgs(fx.create_asset_data(path))
def put(s,n,v):assert s.set_parameter(n,v),n
def f(v):return fx.create_script_input_float(v)
def v(x,y,z):return fx.create_script_input_vector(u.Vector(x,y,z))
def enum(path,name):return fx.create_script_input_enum(path,name)
def dynamic(path,kind,**params):
    s=fx.create_script_context(arg(path))
    for name,value in params.items():put(s,name,value)
    return fx.create_script_input_dynamic(s,kind)
def rand(a,b):return dynamic(P.di_random_range_float,u.NiagaraScriptInputType.FLOAT,Minimum=f(a),Maximum=f(b))
try:
    mat=u.load_asset(root+'/M_OilNiagaraDroplet')
    if not mat:mat=assets.duplicate_asset('M_OilNiagaraDroplet',root,u.load_asset(root+'/M_OilDroplet'))
    mat.set_editor_property('used_with_niagara_mesh_particles',True)
    lib.recompile_material(mat);assert u.EditorAssetLibrary.save_loaded_asset(mat)
    # This script only replaces its own generated system, never user Niagara assets.
    existing=u.load_asset(root+'/NS_OilDroplets')
    assert not existing or '-ProphecyOilRebuild' in u.SystemLibrary.get_command_line(), 'Refusing to replace a potentially hand-edited system without explicit rebuild flag'
    if existing:assert u.EditorAssetLibrary.delete_loaded_asset(existing)
    system=assets.create_asset('NS_OilDroplets',root,u.NiagaraSystem,u.NiagaraSystemFactoryNew())
    ctx=fx.create_system_conversion_context(system)
    e=ctx.add_empty_emitter('Oil_Droplet_Impostors')
    e.set_enabled(True)
    e.set_local_space(True)
    e.set_sim_target(u.NiagaraSimTarget.CPU_SIM)
    cat=u.ScriptExecutionCategory
    def module(name,path,category):return e.find_or_add_module_script(name,arg(path),category)
    state=module('EmitterState','/Niagara/Modules/Emitter/EmitterState.EmitterState',cat.EMITTER_UPDATE)
    put(state,'Life Cycle Mode',enum(P.enum_niagara_emitter_life_cycle_mode,'Self'))
    put(state,'Loop Behavior',enum(P.enum_niagara_emitter_state_options,'Once'))
    put(state,'Loop Duration',f(.1))
    put(state,'Inactive Response',enum(P.enum_niagara_inactive_mode,'Complete (Let Particles Finish then Kill Emitter)'))
    burst=module('Dense_Spray',P.script_spawnburst,cat.EMITTER_UPDATE)
    put(burst,'Spawn Count',fx.create_script_input_int(360));put(burst,'Spawn Time',f(0))
    init=module('InitializeParticle',P.script_initialize_particle,cat.PARTICLE_SPAWN)
    put(init,'Lifetime',rand(.52,.75))
    # Scalar random size preserves a spherical rest shape. Velocity adds X stretch.
    scale=dynamic(P.di_vector_from_float,u.NiagaraScriptInputType.VEC3,Value=rand(.009,.022))
    e.set_parameter_directly('Particles.Scale',scale,cat.PARTICLE_SPAWN)
    vel=module('SprayVelocity',P.script_add_velocity,cat.PARTICLE_SPAWN)
    put(vel,'Velocity Mode',enum(P.enum_niagara_velocity_mode,'In Cone'))
    put(vel,'Velocity Speed',rand(240,400))
    put(vel,'Cone Axis',v(0,0,1));put(vel,'Cone Angle',f(.38))
    put(vel,'Cone Angle Mode',enum(P.enum_niagara_angle_input,'Normalized Angle (0-1)'))
    module('ParticleState',P.script_particle_state,cat.PARTICLE_UPDATE)
    gravity=module('Gravity',P.script_acceleration_force,cat.PARTICLE_UPDATE)
    put(gravity,'Acceleration',v(0,0,-980))
    put(gravity,'Coordinate Space',enum(P.enum_niagara_coordinate_space,'World'))
    module('SolveForcesAndVelocity',P.script_solve_forces_and_velocity,cat.PARTICLE_UPDATE)
    stretch=module('VelocityEllipsoids',P.script_scale_mesh_size_speed,cat.PARTICLE_UPDATE)
    put(stretch,'Max Scale Factor',v(3,1,1))
    # Use speed, not separate XYZ components: renderer faces its X along velocity.
    speed=dynamic(P.di_vector_length_safe,u.NiagaraScriptInputType.FLOAT,Vector=fx.create_script_input_linked_parameter('Particles.Velocity',u.NiagaraScriptInputType.VEC3))
    speedvec=dynamic(P.di_vector_from_float,u.NiagaraScriptInputType.VEC3,Value=speed)
    put(stretch,'Source Velocity',speedvec)
    r=u.NiagaraMeshRendererProperties(); mesh=u.NiagaraMeshRendererMeshProperties()
    sphere=u.load_asset(root+'/SM_OilDroplet')
    if not sphere:
        sphere=assets.duplicate_asset('SM_OilDroplet',root,u.load_asset('/Engine/BasicShapes/Sphere'))
        opts=u.StaticMeshReductionOptions(reduction_settings=[u.StaticMeshReductionSettings(percent_triangles=.125,screen_size=1.)])
        assert u.get_editor_subsystem(u.StaticMeshEditorSubsystem).set_lods(sphere,opts)==1
        assert u.EditorAssetLibrary.save_loaded_asset(sphere)
    mesh.set_editor_property('Mesh',sphere)
    r.set_editor_property('Meshes',[mesh]);r.set_editor_property('FacingMode',u.NiagaraMeshFacingMode.VELOCITY)
    r.set_editor_property('bOverrideMaterials',True)
    override=u.NiagaraMeshMaterialOverride();override.set_editor_property('ExplicitMat',mat)
    r.set_editor_property('OverrideMaterials',[override]);r.set_editor_property('bEnableFrustumCulling',False)
    e.add_renderer('Velocity_Spheres',r)
    ctx.finalize();ctx.cleanup();ctx=None
    assert u.EditorAssetLibrary.save_loaded_asset(system)
    backup=out/'before';backup.mkdir(exist_ok=True)
    disk=Path(u.Paths.project_content_dir())/'_mygame/Tests/Oil'
    for name in ['BP_OilBottle.uasset','M_OilTest.umap']:
        if not (backup/name).exists():shutil.copy2(disk/name,backup/name)
    runpy.run_path(str(Path(__file__).with_name('WireNiagaraSplash.py')))
    (out/'niagara-build.json').write_text(json.dumps({'system':system.get_path_name(),'count':360,'collision':False,'saved':True},indent=2))
    (out/'niagara-error.txt').unlink(missing_ok=True)
except Exception:
    (out/'niagara-error.txt').write_text(traceback.format_exc());u.log_error(traceback.format_exc())
finally:
    if ctx:ctx.cleanup()
    u.SystemLibrary.quit_editor()
