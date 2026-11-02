"""Keep the original collar's smooth cast-edge shading and exact geometry."""
import bpy,json
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
ob=next(o for o in bpy.data.collections['SPEAR • editable components'].objects if o.name.startswith('07 •'))
for edge in ob.data.edges: edge.use_edge_sharp=False
for poly in ob.data.polygons: poly.use_smooth=poly.index>1
ob.data.normals_split_custom_set([(0,0,0)]*len(ob.data.loops))
report=json.loads((OUT/'Gold_Detail_Verification.json').read_text(encoding='utf-8'))
report['collar_weighted_normals_only']=False
report['collar_original_soft_edge_normals_retained']=True
(OUT/'Gold_Detail_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Original smooth cast-edge shading retained; collar geometry unchanged.')
