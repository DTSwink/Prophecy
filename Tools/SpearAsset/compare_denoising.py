"""Two small actual-camera crops; no changes to source materials or geometry."""
import bpy
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s
properties=['use_border','use_crop_to_border','border_min_x','border_max_x','border_min_y','border_max_y','filepath']
state={k:getattr(s.render,k) for k in properties};samples=s.cycles.samples;denoise=s.cycles.use_denoising
try:
 s.render.use_border=True;s.render.use_crop_to_border=True
 s.render.border_min_x=710/1200;s.render.border_max_x=900/1200;s.render.border_min_y=1-570/673;s.render.border_max_y=1-410/673
 s.cycles.samples=64
 for use,name in [(False,'Diagnostic_Wood64_Raw.png'),(True,'Diagnostic_Wood64_Denoised.png')]:
  s.cycles.use_denoising=use;s.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
finally:
 for k,v in state.items():setattr(s.render,k,v)
 s.cycles.samples=samples;s.cycles.use_denoising=denoise
print('64sample wood crops saved; render settings restored.')
