"""Taut scored grip and integral straight keeper collars; accepted head untouched."""
import bpy,bmesh,json,hashlib,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');WORK=ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components']
mat=bpy.data.materials['M_ImperialSpear_PBR']
allowed=('03 •','04 •','Grip •')
def hash_mesh(o):
    return hashlib.sha256(json.dumps({'v':[list(v.co) for v in o.data.vertices],'f':[list(p.vertices) for p in o.data.polygons],
                                     'uv':[list(v.uv) for v in o.data.uv_layers['UV0_SurfaceAtlas'].data]},separators=(',',':')).encode()).hexdigest()
protected={o.name:hash_mesh(o) for o in art.objects if o.type=='MESH' and not o.name.startswith(allowed)}
old=[o for o in art.objects if o.type=='MESH' and o.name.startswith(allowed)]
assert len(old) in (8,3),[o.name for o in old]
leather_uv=(.5029296875,.7470703125,.0732421875,.4970703125)
gold_uv=(.5029296875,.7470703125,.0029296875,.0673828125)

def lathe(name,profile,region,sides):
    verts=[(r*math.cos(j*math.tau/sides),r*math.sin(j*math.tau/sides),z) for z,r in profile for j in range(sides)]
    faces=[];uvs=[];normals=[]
    u0,u1,v0,v1=region
    def uv(u,v):return (u0+(u1-u0)*u,v0+(v1-v0)*v)
    for k in range(len(profile)-1):
        z0,r0=profile[k];z1,r1=profile[k+1];dz,dr=z1-z0,r1-r0
        for j in range(sides):
            faces.append((k*sides+j,k*sides+(j+1)%sides,(k+1)*sides+(j+1)%sides,(k+1)*sides+j))
            lo=(z0-profile[0][0])/(profile[-1][0]-profile[0][0]);hi=(z1-profile[0][0])/(profile[-1][0]-profile[0][0])
            uvs.extend([uv(j/sides,lo),uv((j+1)/sides,lo),uv((j+1)/sides,hi),uv(j/sides,hi)])
            # Smooth around the circumference, retain each machined axial face.
            for jj in (j,j+1,j+1,j):
                a=jj*math.tau/sides;normals.append(tuple(Vector((dz*math.cos(a),dz*math.sin(a),-dr)).normalized()))
    faces.extend([tuple(reversed(range(sides))),tuple((len(profile)-1)*sides+j for j in range(sides))])
    for side,order in ((-1,reversed(range(sides))),(1,range(sides))):
        for j in order:
            uvs.append(uv(.5+.44*math.cos(j*math.tau/sides),.015+.003*math.sin(j*math.tau/sides)))
            normals.append((0,0,side))
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    data.materials.append(mat);layer=data.uv_layers.new(name='UV0_SurfaceAtlas');layer.active_render=True
    for i,value in enumerate(uvs):layer.data[i].uv=value
    for p in data.polygons:p.use_smooth=True
    data.normals_split_custom_set(normals);data.update()
    bm=bmesh.new();bm.from_mesh(data);closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free()
    assert closed and volume>0,(name,closed,volume)
    ob=bpy.data.objects.new('TEMP '+name,data);art.objects.link(ob)
    return ob,{'name':name,'triangles':sum(len(p.vertices)-2 for p in data.polygons),'closed':closed,'volume_m3':volume,'uv_region':region}

new=[];reports=[]
grip,report=lathe('03 • scored leather handgrip',[(1.115,.0175),(1.121,.01825),(1.128,.0185),(1.342,.0185),(1.349,.01825),(1.355,.0175)],leather_uv,64)
new.append(grip);reports.append(report)
for index,z in enumerate((1.112,1.358)):
    start,end=(.0163,.0184) if index==0 else (.0184,.0163)
    profile=[(z-.010,start),(z-.010,.0201),(z-.0098,.0203),(z-.0094,.0205),(z-.0086,.0205),(z-.0077,.0196),
             (z+.0077,.0196),(z+.0086,.0205),(z+.0094,.0205),(z+.0098,.0203),(z+.010,.0201),(z+.010,end)]
    ob,report=lathe('Grip • chased straight keeper '+('lower' if index==0 else 'upper'),profile,gold_uv,48)
    new.append(ob);reports.append(report)
assert all(hash_mesh(bpy.data.objects[name])==digest for name,digest in protected.items())
for ob in old:bpy.data.objects.remove(ob,do_unlink=True)
for ob,report in zip(new,reports):ob.name=report['name']
assert all(hash_mesh(bpy.data.objects[name])==digest for name,digest in protected.items())
s['Spear_revision']='07 WIP: final handle materials and angular S relief'
s['Accepted_spearhead_preserved_except_requested_S_relief']=True
report={'components':reports,'protected_components_unchanged':len(protected),'grip_span_m':[1.115,1.355],'grip_pivot_m':1.235,
        'gold_keeper_bounds_m':[[1.102,1.122],[1.348,1.368]],'changes':'Removed puffy spiral winding; taut sleeve and collars with integral rims'}
(WORK/'Handle_Geometry_Report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print(json.dumps(report))
