import unreal,json,pathlib,sys
folder='/Game/_mygame/assets/holster/Animated';name='BP_HolsterWithStrap'
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world(),'Preserve user Play'
bp=unreal.load_asset(folder+'/'+name)
assert not bp or '--repair-generated' in sys.argv,'Do not overwrite user Blueprint'
if not bp:
    factory=unreal.BlueprintFactory();factory.set_editor_property('parent_class',unreal.Actor)
    bp=unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,folder,unreal.Blueprint,factory)
assert bp
sub=unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem);lib=unreal.SubobjectDataBlueprintFunctionLibrary
handles=sub.k2_gather_subobject_data_for_blueprint(bp)
parent=next(h for h in handles if isinstance(lib.get_object_for_blueprint(lib.get_data(h),bp),unreal.SceneComponent))
def add(parent,cls,name):
    h=next((h for h in sub.k2_gather_subobject_data_for_blueprint(bp) if str(lib.get_variable_name(lib.get_data(h)))==name),None)
    if h is None:
        params=unreal.AddNewSubobjectParams(parent_handle=parent,new_class=cls,blueprint_context=bp,conform_transform_to_parent=True)
        h,reason=sub.add_new_subobject(params=params);assert not str(reason),str(reason)
        assert sub.rename_subobject(h,unreal.Text(name))
    obj=lib.get_object_for_blueprint(lib.get_data(h),bp);assert obj
    obj.set_relative_transform(unreal.Transform(),False,True)
    obj.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION);obj.set_editor_property('generate_overlap_events',False)
    return h,obj
body_h,body=add(parent,unreal.StaticMeshComponent,'holster')
body.set_static_mesh(unreal.load_asset(folder+'/HolsterRigid'));body.set_mobility(unreal.ComponentMobility.MOVABLE)
strap_h,strap=add(body_h,unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyHolsterStrapComponent'),'Strap')
strap.set_skeletal_mesh_asset(unreal.load_asset(folder+'/HolsterStrap'))
anim=unreal.load_class(None,folder+'/ABP_HolsterStrap.ABP_HolsterStrap_C')
strap.set_anim_instance_class(anim or unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyHolsterStrapAnimInstance'))
strap.set_editor_property('bounds_scale',2.)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,only_if_is_dirty=False)
out=pathlib.Path(unreal.Paths.project_dir()).resolve()/'Saved/Diagnostics/HolsterStrap20261013'
(out/'blueprint.json').write_text(json.dumps({'path':bp.get_path_name(),'components':['holster','Strap'],'mesh':strap.get_skinned_asset().get_path_name(),'distance_cm':strap.get_editor_property('max_simulation_distance'),'enabled':strap.get_editor_property('strap_enabled')},indent=2))
print('HOLSTER_BLUEPRINT_READY',bp.get_path_name())
