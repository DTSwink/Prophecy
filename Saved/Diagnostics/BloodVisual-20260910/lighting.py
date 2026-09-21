import builtins,unreal
s=builtins._blood_visual
for old in unreal.GameplayStatics.get_all_actors_of_class(s['world'],unreal.RectLight):
 if 'BloodVisual20260910' in [str(t) for t in old.tags]:unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(old)
for name in ('static','nanite','sword','character'):
 cam=s['actors']['camera_'+name]
 a=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.RectLight,cam.get_actor_location(),cam.get_actor_rotation(),transient=False)
 a.tags=['BloodVisual20260910','BloodCheck_light_'+name];a.set_actor_label('BloodCheck_light_'+name)
 c=a.get_component_by_class(unreal.RectLightComponent)
 c.set_mobility(unreal.ComponentMobility.MOVABLE)
 for key,value in {'intensity':80.,'attenuation_radius':1200.,'source_width':250.,'source_height':250.}.items():c.set_editor_property(key,value)
 c.set_cast_shadows(False)
 s['actors']['light_'+name]=a
print('BLOOD_LIGHTING_READY')
