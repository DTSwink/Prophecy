import unreal
for cls,names in [(unreal.Actor,['add_component_by_class']), (unreal.GameplayStatics,['begin_deferred_actor_spawn_from_class','finish_spawning_actor']), (unreal.AutomationLibrary,['take_high_res_screenshot']), (unreal.ProphecyJoltBlueprintLibrary,['initialize_jolt_world']), (unreal.HitResult,[]), (unreal.SceneCaptureComponent2D,['capture_scene'])]:
 print(cls.__name__,cls.__doc__ if not names else '')
 for name in names: print(name,getattr(cls,name).__doc__ if hasattr(cls,name) else 'unavailable')
print('MANAGER DEFAULTS')
cl=unreal.EditorAssetLibrary.load_blueprint_class('/Game/Prophecy/BloodTexturePainting/BP_BloodPaintManager')
d=unreal.get_default_object(cl)
print('PAIRS',[(str(p.clean_material),str(p.blood_material)) for p in d.blood_enabled_material_pairs])
print('GENERATED',unreal.EditorAssetLibrary.list_assets('/Game/Prophecy/BloodTexturePainting/Generated',True,False))
print('LEVEL',unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_path_name())
