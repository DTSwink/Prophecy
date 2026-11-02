import bpy,json,shutil
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear';BACK=ROOT/'Saved/Diagnostics/ImperialSpear/BeforeSevenPointCorrections_v1'
if not BACK.exists():
 BACK.mkdir(parents=True);shutil.copy2(bpy.data.filepath,BACK/'Source.blend');shutil.copytree(OUT/'Textures',BACK/'Textures')
art=bpy.data.collections['SPEAR • editable components'];result={}
for ob in art.objects:
 if ob.type!='MESH' or not ob.name.startswith(('05 •','07 •','Socket •','Blade • flame','Tassel • pierced')):continue
 vs=[tuple(ob.matrix_world@v.co) for v in ob.data.vertices]
 result[ob.name]={'vertices':vs,'faces':[list(p.vertices) for p in ob.data.polygons],'bounds':[[min(p[i] for p in vs) for i in range(3)],[max(p[i] for p in vs) for i in range(3)]],'custom_normals':ob.data.has_custom_normals}
(OUT/'Seven_Point_Fit_Probe.json').write_text(json.dumps(result),encoding='utf-8')
print(json.dumps({n:{k:v for k,v in d.items() if k not in ('vertices','faces')} for n,d in result.items()}))
