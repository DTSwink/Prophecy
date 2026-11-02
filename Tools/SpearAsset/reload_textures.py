import bpy
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
for image in bpy.data.images:
    if image.name.startswith('T_ImperialSpear_') and image.source=='FILE':
        image.filepath=str(OUT/'Textures'/(image.name.split('.png')[0]+'.png')); image.reload()
print('Atlas refreshed; no geometry changes.')
