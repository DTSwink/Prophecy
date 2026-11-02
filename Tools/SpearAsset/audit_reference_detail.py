"""Audit the live source checkpoint; intentionally does not validate old exports."""
import bpy,bmesh,json,math,hashlib
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
art=bpy.data.collections['SPEAR • editable components']
def fingerprint(ob):
 data={'vertices':[tuple(v.co) for v in ob.data.vertices],'faces':[tuple(p.vertices) for p in ob.data.polygons]}
 return hashlib.sha256(json.dumps(data,separators=(',',':')).encode()).hexdigest()
baseline=json.loads((OUT/'Reference_Rebuild_Verification.json').read_text(encoding='utf-8'))
checks={name:fingerprint(bpy.data.objects[name])==digest for name,digest in baseline['protected_geometry_sha256'].items()}
assert all(checks.values()),[name for name,value in checks.items() if not value]
objects=[o for o in art.objects if o.type=='MESH'];finite=all(math.isfinite(c) for o in objects for v in o.data.vertices for c in v.co)
assert finite
assert not [o.name for o in art.objects if o.name.startswith('TEMP')]
body=next(o for o in objects if o.name.startswith('07 •'));bm=bmesh.new();bm.from_mesh(body.data);closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free()
assert closed and volume>0
assert len(body.data.uv_layers)==1 and body.data.uv_layers[0].name=='UV0_SurfaceAtlas' and body.data.uv_layers[0].active_render
report={'status':'SOURCE_DETAIL_CHECKPOINT_ONLY','source_blend':bpy.data.filepath,'source_objects':len(objects),'source_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects),'finite_positions':finite,'protected_geometry_checks':checks,'housing_closed':closed,'housing_volume_m3':volume,'housing_uv_layers':[u.name for u in body.data.uv_layers],'export_status':'Older FBX/GLB/LOD/collision still pending regeneration','appearance_status':'Reference matching remains under review'}
(OUT/'Current_Detail_Audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='protected_geometry_checks'}))
