"""One 2x still at three CPU threads to preserve grain at viewing size."""
import bpy
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s
for image in bpy.data.images:
 if image.name.startswith('T_ImperialSpear_') and image.source=='FILE':
  image.filepath=str(OUT/'Textures'/(image.name.split('.png')[0]+'.png'));image.reload()
  if '_ORM' in image.name:image.alpha_mode='CHANNEL_PACKED';image.colorspace_settings.name='Non-Color'
state=(s.render.resolution_x,s.render.resolution_y,s.cycles.samples,s.cycles.use_denoising,s.render.filepath)
try:
 s.render.resolution_x=2400;s.render.resolution_y=1346;s.cycles.samples=32;s.cycles.use_denoising=True
 s.render.filepath=str(OUT/'Comparison_Current.png');bpy.ops.render.render(write_still=True)
finally:
 s.render.resolution_x,s.render.resolution_y,s.cycles.samples,s.cycles.use_denoising,s.render.filepath=state
 bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print('2x same-pose still saved; ordinary render settings restored.')
