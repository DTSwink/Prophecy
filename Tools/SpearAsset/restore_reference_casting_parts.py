import bpy,json,shutil
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
art=bpy.data.collections['SPEAR • editable components']; mat=next(o for o in art.objects if o.name.startswith('06 •')).data.materials[0]
prefixes=('07 •','Socket • continuous cast inverted S')
saved=ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'
recovery=ROOT/'Saved/Diagnostics/ImperialSpear/ReferencePartsRecovery.blend'
if not recovery.exists(): shutil.copy2(saved,recovery)
with bpy.data.libraries.load(str(recovery),link=False) as (src,dst):
 dst.objects=[name for name in src.objects if name.startswith(prefixes)]
for ob in list(art.objects):
 if ob.name.startswith(prefixes): bpy.data.objects.remove(ob,do_unlink=True)
for ob in dst.objects:
 art.objects.link(ob); ob.data.materials.clear(); ob.data.materials.append(mat)
print('Restored only the owned housing and two relief meshes to the last saved reference checkpoint.')
