"""Run the exporter's read-only preflight against the live source."""
from pathlib import Path
path=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Tools/SpearAsset/export_spear.py')
text=path.read_text(encoding='utf-8')
prefix=text.split('\ndef carry_surface_data',1)[0]
assert 'bpy.data.objects.remove' not in prefix
exec(compile(prefix,str(path),'exec'))
print('Preflight passed:',len(source_meshes),'editable meshes;',len(specs),'assembly hull specifications plus four blade pieces.')
