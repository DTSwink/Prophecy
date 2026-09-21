import unreal,builtins
s=builtins._blood_visual;l=s['fighter_light'];lc=l.get_component_by_class(unreal.RectLightComponent);cap=s['fighter_capture'];cc=cap.get_component_by_class(unreal.SceneCaptureComponent2D)
print('LIGHT',l.get_actor_transform(),lc.mobility,lc.intensity,lc.intensity_units,lc.is_visible(),lc.affects_world,lc.lighting_channels,lc.attenuation_radius)
for a in unreal.GameplayStatics.get_all_actors_of_class(l.get_world(),unreal.ProphecyAgent):
 for c in a.get_components_by_class(unreal.SkeletalMeshComponent):print('MESH',c.get_name(),c.lighting_channels)
print('CAPTURE',cap.get_actor_transform(),cc.post_process_settings)
