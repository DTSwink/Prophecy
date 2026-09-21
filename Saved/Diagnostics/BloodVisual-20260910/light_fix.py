import unreal,builtins
s=builtins._blood_visual
for a in unreal.EditorLevelLibrary.get_all_level_actors():
 if 'BloodVisual20260910' not in [str(t) for t in a.tags]:continue
 for c in a.get_components_by_class(unreal.LightComponent):
  if isinstance(c,unreal.RectLightComponent):c.set_intensity(8)
  print(a.get_actor_label(),'light intensity',c.get_editor_property('intensity'))
c=s['actors']['Capture'].get_component_by_class(unreal.SceneCaptureComponent2D)
pp=c.post_process_settings
print('CAPTURE',c.capture_source,pp.auto_exposure_method,pp.auto_exposure_bias,pp.override_auto_exposure_bias,c.post_process_blend_weight)
print('SCENE',unreal.EditorLevelLibrary.get_editor_world().get_path_name())
