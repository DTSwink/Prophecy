import unreal as u
from pathlib import Path
assert '-ProphecyOilStudio' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
w=ed.get_editor_world();actors=u.get_editor_subsystem(u.EditorActorSubsystem)
a=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewBottle')
c=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='StudioReviewCamera').get_component_by_class(u.SceneCaptureComponent2D)
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Studio'
u.SystemLibrary.execute_console_command(w,'r.RefractionQuality 0')
for _ in range(4):c.capture_scene()
u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),'no-refraction.png')
# Retain low-cost material lighting, turn off SSR to isolate the environment.
g=u.load_asset('/Game/_mygame/OilBottle/Materials/M_OilBottleGlass')
mid=a.bottle.create_dynamic_material_instance(0);mid.set_scalar_parameter_value('IOR',1.02)
u.SystemLibrary.execute_console_command(w,'r.RefractionQuality 2')
for _ in range(4):c.capture_scene()
u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),'ior102.png')
print('AB_COMPLETE')
