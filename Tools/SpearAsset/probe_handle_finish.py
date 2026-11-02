"""Capture the accepted source and exact handle UV usage before refinement."""
import bpy,json,hashlib,math
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy')
OUT=ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish';OUT.mkdir(exist_ok=True,parents=True)
art=bpy.data.collections['SPEAR • editable components'];rows={};baseline={}
def digest(data):return hashlib.sha256(json.dumps(data,separators=(',',':')).encode()).hexdigest()
for ob in art.objects:
    if ob.type!='MESH':continue
    m=ob.data;uv=m.uv_layers['UV0_SurfaceAtlas']
    geo={'vertices':[list(v.co) for v in m.vertices],'faces':[list(p.vertices) for p in m.polygons]}
    baseline[ob.name]={'geometry':digest(geo),'uv':digest([list(v.uv) for v in uv.data])}
    row={'vertices':len(m.vertices),'triangles':sum(len(p.vertices)-2 for p in m.polygons),
         'bounds':{'min':[min(v.co[k] for v in m.vertices) for k in range(3)],'max':[max(v.co[k] for v in m.vertices) for k in range(3)]},
         'uv_bounds':{'min':[min(v.uv[k] for v in uv.data) for k in range(2)],'max':[max(v.uv[k] for v in uv.data) for k in range(2)]}}
    if ob.name.startswith(('01 •','03 •','04 •','Grip •','Socket • continuous cast inverted S')):
        row.update(geo);row['uv']=[list(v.uv) for v in uv.data];row['smooth']=[p.use_smooth for p in m.polygons]
    rows[ob.name]=row
mat=bpy.data.materials['M_ImperialSpear_PBR']
nodes=[{'name':n.name,'type':n.type,'normal_strength':n.inputs['Strength'].default_value if n.type=='NORMAL_MAP' else None,
        'image':n.image.name if n.type=='TEX_IMAGE' and n.image else None,'color_space':n.image.colorspace_settings.name if n.type=='TEX_IMAGE' and n.image else None} for n in mat.node_tree.nodes]
report={'objects':rows,'shader_nodes':nodes}
(OUT/'Handle_Probe.json').write_text(json.dumps(report),encoding='utf-8')
path=OUT/'Accepted_Baseline.json'
assert not path.exists(),'Do not overwrite accepted baseline'
path.write_text(json.dumps(baseline,indent=2),encoding='utf-8')
print(json.dumps({'handle':{n:{k:v for k,v in r.items() if k not in ('vertices','faces','uv','smooth')} for n,r in rows.items() if n.startswith(('01 •','03 •','04 •','Grip •'))},'shader_nodes':nodes}))
