import unreal,builtins,json
s=builtins._blood_visual;w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();assert w.get_path_name()=='/Game/testNN.testNN'
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
e=unreal.get_editor_subsystem(unreal.EditorActorSubsystem);actors=e.get_all_level_actors()
assert not [a for a in actors if isinstance(a,unreal.ProphecyBloodTexturePaintManager) or 'DecalManager' in a.get_class().get_name()]
bp=unreal.load_asset('/Game/Prophecy/BloodTexturePainting/BP_BloodPaintManager');cls=unreal.EditorAssetLibrary.load_blueprint_class('/Game/Prophecy/BloodTexturePainting/BP_BloodPaintManager');cdo=unreal.get_default_object(cls)
manager=e.spawn_actor_from_class(cls,unreal.Vector(0,0,-1000));manager.set_actor_label('BloodPaintManager')
manager.brush_material=unreal.load_asset('/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle')
manager.blood_enabled_material_pairs=[unreal.ProphecyBloodMaterialPair(clean_material=unreal.load_asset(p['clean']),blood_material=unreal.load_asset(p['blood'])) for p in json.loads((s['out']/'stage.json').read_text())['material_pairs']]
manager.editor_auto_create_blood_materials=True;manager.editor_auto_update_blood_materials=False;manager.editor_allow_generated_material_overwrite=False;manager.editor_save_generated_blood_materials=True
for a in actors:
 if isinstance(a,unreal.ProphecyAgent):
  for c in a.get_components_by_class(unreal.SkeletalMeshComponent):
   for slot in range(c.get_num_materials()):
    assert manager.debug_paint_uv(c,unreal.Vector2D(.5,.5),1,0,slot),(c.get_path_name(),slot)
    manager.clear_runtime_paint_state(True)
manager.editor_auto_create_blood_materials=False
cdo.blood_enabled_material_pairs=manager.blood_enabled_material_pairs;cdo.brush_material=manager.brush_material
cdo.editor_auto_create_blood_materials=False;cdo.editor_auto_update_blood_materials=False
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
floor=next(a for a in actors if a.get_name()=='Floor_0');assert floor.static_mesh_component.mobility==unreal.ComponentMobility.STATIC
decal=e.spawn_actor_from_class(unreal.EditorAssetLibrary.load_blueprint_class('/Game/_mygame/blood2/A_DecalManager'),unreal.Vector(0,0,-1000));decal.set_actor_label('BloodDecalManager');decal.set_editor_property('paint manager',manager);decal.set_editor_property('floor',floor)
assert unreal.EditorLoadingAndSavingUtils.save_map(w,'/Game/testNN')
report={'manager':manager.get_path_name(),'decal_manager':decal.get_path_name(),'floor':floor.get_path_name(),'pairs':[{'clean':p.clean_material.get_path_name(),'blood':p.blood_material.get_path_name()} for p in manager.blood_enabled_material_pairs],'blueprint_saved':True,'map_saved':True,'auto_generation':manager.editor_auto_create_blood_materials}
(s['out']/'production-configuration.json').write_text(json.dumps(report,indent=2));print('BLOOD_CONFIGURATION_SAVED',report)
s.pop('fighter_manager',None);s.pop('fighter_capture',None)
