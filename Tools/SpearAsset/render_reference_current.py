import bpy
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
scene.render.filepath=str(OUT/'Comparison_Current.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
bpy.ops.render.render(write_still=True)
print('Current reference-pose comparison rendered.')
