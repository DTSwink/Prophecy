import unreal,builtins,json
s=builtins._blood_visual;assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world();assert w.get_path_name()=='/Game/testNN.testNN'
bp=unreal.load_asset('/Game/Prophecy/BloodTexturePainting/BP_BloodPaintManager');cdo=unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class('/Game/Prophecy/BloodTexturePainting/BP_BloodPaintManager'))
cdo.set_debug_show_mask_on_painted_materials(False)
managers=[a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.ProphecyBloodTexturePaintManager)];assert len(managers)==1
managers[0].set_debug_show_mask_on_painted_materials(False)
unreal.BlueprintEditorLibrary.compile_blueprint(bp);assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False);assert unreal.EditorLoadingAndSavingUtils.save_map(w,'/Game/testNN')
report={'mask_debug_disabled_on_blueprint':not cdo.debug_show_mask_on_painted_materials,'mask_debug_disabled_on_placed_actor':not managers[0].debug_show_mask_on_painted_materials}
(s['out']/'display-defaults.json').write_text(json.dumps(report,indent=2));print(report)
