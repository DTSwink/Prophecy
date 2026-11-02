import bpy,json,hashlib
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
report=json.loads((OUT/'Gold_Detail_Verification.json').read_text(encoding='utf-8'))
for name,digest in report['protected_geometry_sha256'].items():
    o=bpy.data.objects[name]
    d={'vertices':[tuple(v.co) for v in o.data.vertices],'faces':[tuple(p.vertices) for p in o.data.polygons]}
    assert hashlib.sha256(json.dumps(d,separators=(',',':')).encode()).hexdigest()==digest,name
source=bpy.data.scenes['Scene']; game=bpy.data.scenes['GAME • Unreal export']
assert len([o for o in game.objects if o.name.startswith('UCX_')])==11
for image in bpy.data.images:
    if image.source=='FILE': assert Path(bpy.path.abspath(image.filepath)).is_file(),image.filepath
report['final_saved_geometry_check']={'protected_components':len(report['protected_geometry_sha256']),'all_unchanged':True,'collision_hulls':11,'texture_paths_exist':True}
(OUT/'Gold_Detail_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report['final_saved_geometry_check']))
