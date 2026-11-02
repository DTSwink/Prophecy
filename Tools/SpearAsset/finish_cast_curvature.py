"""Local interpolation of the two hero scrolls, keeping their backs seated."""
import bpy,bmesh,ast,math,json,hashlib
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
scene=bpy.data.scenes['Scene']; bpy.context.window.scene=scene
art=bpy.data.collections['SPEAR • editable components']
blade=next(o for o in art.objects if o.name.startswith('06 •'))
mat=blade.data.materials[0]
regions={'gold':(.5,.75,.5,1),'gold_shadow':(.75,.8125,.5,1)}
tree=ast.parse((ROOT/'Tools/SpearAsset/build_spear.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'atlas','mesh'}],type_ignores=[]),'helpers','exec'))
bvh=BVHTree.FromObject(blade,bpy.context.evaluated_depsgraph_get())
def depth(p,side):
    hit=bvh.ray_cast(Vector((p.x,side*.2,p.z)),Vector((0,-side,0)),.4)[0]
    assert hit is not None
    return abs(hit.y)
def cubic(a,b,c,d,t):
    return .5*(2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
counts=[]
for ob in list(art.objects):
    if not ob.name.startswith('Blade • crown cast scroll') or ob.get('Curvature_finished'): continue
    old=[v.co.copy() for v in ob.data.vertices]; nr=len(old)//9; side=-1 if old[0].y<0 else 1
    offsets=[side*p.y-depth(p,side) for p in old]
    vs=[]
    for i in range(nr-1):
        for t in [0,.5]:
            for j in range(9):
                ids=[max(0,i-1)*9+j,i*9+j,(i+1)*9+j,min(nr-1,i+2)*9+j]
                p=cubic(*(old[k] for k in ids),t)
                h=cubic(*(offsets[k] for k in ids),t)
                p.y=side*(depth(p,side)+h); vs.append(tuple(p))
    vs.extend(tuple(v) for v in old[-9:]); n=len(vs)//9
    fs=[(i*9+j,i*9+(j+1)%9,(i+1)*9+(j+1)%9,(i+1)*9+j) for i in range(n-1) for j in range(9)]
    fs.extend([tuple(reversed(range(9))),tuple((n-1)*9+j for j in range(9))])
    name=ob.name; replacement=mesh(name+' refined',vs,fs,'gold',smooth=True)
    for p in replacement.data.polygons:
        cap=p.index>=9*(n-1); p.use_smooth=not cap
        kind='gold_shadow' if not cap and p.index%9 in [0,5,6,7,8] else 'gold'
        for li in p.loop_indices:
            vi=replacement.data.loops[li].vertex_index; row,col=divmod(vi,9)
            replacement.data.uv_layers[0].data[li].uv=atlas(col/8,row/(n-1),kind)
    bm=bmesh.new(); bm.from_mesh(replacement.data)
    assert all(e.is_manifold for e in bm.edges); bm.free()
    bpy.data.objects.remove(ob,do_unlink=True); replacement.name=name
    replacement['Curvature_finished']=True
    counts.append({'name':name,'stations':n,'vertices':len(vs),'closed':True,'back_seated':True})
report=json.loads((OUT/'Gold_Detail_Verification.json').read_text(encoding='utf-8'))
report['hero_scroll_curve_finish']=counts
for name,digest in report['protected_geometry_sha256'].items():
    o=bpy.data.objects[name]; d={'vertices':[tuple(v.co) for v in o.data.vertices],'faces':[tuple(p.vertices) for p in o.data.polygons]}
    assert hashlib.sha256(json.dumps(d,separators=(',',':')).encode()).hexdigest()==digest
(OUT/'Gold_Detail_Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(counts))
