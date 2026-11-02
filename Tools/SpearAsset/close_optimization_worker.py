import bpy,os
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');O=R/'Saved/Diagnostics/ImperialSpear/Optimization20261028'
assert os.getpid()==int((O/'blender.pid').read_text().strip())
assert Path(bpy.data.filepath)==R/'Exports/ImperialSpear/ImperialSpear_Optimized.blend'
bpy.app.timers.register(lambda:bpy.ops.wm.quit_blender(),first_interval=2)
print('Optimization worker closing; user Blender untouched.')
