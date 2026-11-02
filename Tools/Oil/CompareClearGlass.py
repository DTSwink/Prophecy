"""Read-only/unsaved glass isolation photographs in the owned review scene."""
import unreal as u
from pathlib import Path
assert '-ProphecyOilClearReview' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
actors=u.get_editor_subsystem(u.EditorActorSubsystem);w=ed.get_editor_world()
a=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='ClearBottleReview')
liquid=a.get_component_by_class(u.ProphecyOilLiquid);liquid.refresh_liquid()
base=a.get_actor_location();eye=base+u.Vector(40,-80,65);target=base+u.Vector(0,0,12)
cam=actors.spawn_actor_from_class(u.SceneCapture2D,eye,u.MathLibrary.find_look_at_rotation(eye,target))
c=cam.get_component_by_class(u.SceneCaptureComponent2D);c.capture_every_frame=False;c.capture_on_movement=False;c.always_persist_rendering_state=True
c.capture_source=u.SceneCaptureSource.SCS_FINAL_COLOR_LDR;c.fov_angle=45
c.texture_target=u.RenderingLibrary.create_render_target2d(w,960,720,u.TextureRenderTargetFormat.RTF_RGBA8)
out=Path(u.Paths.project_saved_dir()).resolve()/'Diagnostics/Oil/Bottle/Clear'
material=a.bottle.get_material(0);mid=a.bottle.create_dynamic_material_instance(0)
for label,fade in [('glass',1),('no-glass',0)]:
    mid.set_scalar_parameter_value('FragmentOpacity',fade)
    for _ in range(3):c.capture_scene()
    u.RenderingLibrary.export_render_target(w,c.texture_target,str(out),label+'.png')
a.bottle.set_material(0,material);actors.destroy_actor(cam)
print('GLASS_AB_DONE')
