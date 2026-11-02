"""Offline Fab GLB conversion + watertight Voronoi glass fracture (manifold3d 3.5.4).
Keeps the 88KB licensed source locally; no geometry code or fracture at runtime.
"""
import json, struct, hashlib
from pathlib import Path
import numpy as np
import manifold3d as mf
from scipy.spatial import ConvexHull

root=Path(__file__).resolve().parents[2]
source=root/'Tools/Oil/Source/MilkBottle.glb'
b=source.read_bytes();n=struct.unpack_from('<I',b,12)[0]
j=json.loads(b[20:20+n]);raw=b[28+n:]
out=root/'Saved/Diagnostics/Oil/Bottle';out.mkdir(parents=True,exist_ok=True)
def accessor(i):
    a=j['accessors'][i];v=j['bufferViews'][a['bufferView']]
    dtype={5126:'<f4',5123:'<u2',5125:'<u4'}[a['componentType']]
    width={'SCALAR':1,'VEC2':2,'VEC3':3}[a['type']]
    return np.frombuffer(raw,dtype=dtype,count=a['count']*width,offset=v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,width).copy()
def get(mesh):
    p=j['meshes'][mesh]['primitives'][0];a=p['attributes']
    return accessor(a['POSITION']).astype(float),accessor(a['NORMAL']).astype(float),accessor(a['TEXCOORD_0']),accessor(p['indices']).reshape(-1,3)

# Preserve original local geometry and relative dimensions, recenter/stand upright.
# GLB's cork is exported beside the mouth: seat it on the bottle axis for the game asset.
v,norm,uv,tri=get(1)
scale=26/(v[:,1].max()-v[:,1].min())
base=v[:,1].min();v[:,1]-=base;v*=scale
v=v[:,[0,2,1]];norm=norm[:,[0,2,1]];tri=tri[:,[0,2,1]] # Y-up RH -> UE Z-up LH
cv,cn,cu,ct=get(0)
cv*=j['nodes'][0]['scale'][0]/j['nodes'][1]['scale'][0]*scale
cv=cv[:,[0,2,1]];cn=cn[:,[0,2,1]];ct=ct[:,[0,2,1]]
cv[:,:2]-=(cv[:,:2].min(axis=0)+cv[:,:2].max(axis=0))/2
cv[:,2]+=26-cv[:,2].min()-1.2

def manifold(v,n,uv,t):
    # This GLB stops its inner neck at one planar open ring. Seal that hidden
    # ring under the cork before boolean processing; reject any other topology.
    from collections import defaultdict
    keys=[tuple(np.round(p,5)) for p in v];edges=defaultdict(list)
    for a,b,c in t:
        for x,y in [(a,b),(b,c),(c,a)]:edges[tuple(sorted((keys[x],keys[y])))].append((x,y))
    boundary=[e[0] for e in edges.values() if len(e)==1]
    if boundary:
        ids=sorted(set(i for e in boundary for i in e));points=v[ids]
        assert len(boundary)==32 and np.ptp(points[:,2])<1e-4
        index=len(v);v=np.vstack([v,points.mean(axis=0)]);n=np.vstack([n,[0,0,1]]);uv=np.vstack([uv,[.5,.5]])
        t=np.vstack([t,[(b,a,index) for a,b in boundary]])
    # Weld positional seams while retaining independent normals and UV properties.
    first={};fr=[];to=[]
    for i,p in enumerate(v):
        key=tuple(np.round(p,5))
        if key in first:fr.append(i);to.append(first[key])
        else:first[key]=i
    mesh=mf.Mesh(np.asarray(np.c_[v,n,uv],dtype=np.float32),np.asarray(t,dtype=np.uint32),
        np.asarray(fr,dtype=np.uint32),np.asarray(to,dtype=np.uint32))
    result=mf.Manifold(mesh)
    assert result.status()==mf.Error.NoError,(result.status(),len(v),len(t))
    assert result.volume()>0
    return result
solid=manifold(v,norm,uv,tri);cork=manifold(cv,cn,cu,ct)
# The export has no full-depth inner wall. Bake a glass cavity once, retaining
# the exact exterior. The sealed neck is covered by the cork.
glass=solid-solid.scale((.93,.93,.98)).translate((0,0,.25))
assert glass.status()==mf.Error.NoError and glass.volume()>0
def geometry(name,m,slot):
    m=m.calculate_normals(0,45);mesh=m.to_mesh();props=np.asarray(mesh.vert_properties)
    return {'name':name,'vertices':props.tolist(),'triangles':np.asarray(mesh.tri_verts).reshape(-1).tolist(),
            'slots':[slot]*m.num_tri(),'volume':m.volume()}
whole=geometry('SM_OilBottle',glass,0);cap=geometry('cap',cork,1)
offset=len(whole['vertices']);whole['vertices']+=cap['vertices'];whole['triangles'] += [i+offset for i in cap['triangles']];whole['slots']+=cap['slots']
whole['volume']+=cap['volume'];meshes=[whole]
# Deterministic farthest-point seeds on the actual shell; no volatile random bake.
centers=v[tri].mean(axis=1)
seeds=[centers[np.argmax(centers[:,2])]]
for _ in range(18):
    d=((centers[:,None,:]-np.array(seeds)[None,:,:])**2).sum(axis=2).min(axis=1)
    seeds.append(centers[np.argmax(d)])
seeds=np.array(seeds)
for _ in range(8):
    labels=((centers[:,None,:]-seeds[None,:,:])**2).sum(axis=2).argmin(axis=1)
    seeds=np.array([centers[labels==k].mean(axis=0) for k in range(19)])
volumes=[]
for i,a in enumerate(seeds):
    piece=glass
    for k,c in enumerate(seeds):
        if k==i:continue
        normal=a-c;normal/=np.linalg.norm(normal)
        piece=piece.trim_by_plane(tuple(normal),float(np.dot(normal,(a+c)/2)))
    assert not piece.is_empty() and piece.status()==mf.Error.NoError
    meshes.append(geometry(f'SM_OilFragment_{i:02}',piece,0));volumes.append(piece.volume())
meshes.append(geometry('SM_OilFragment_19',cork,1))
assert abs(sum(volumes)-glass.volume())<glass.volume()*1e-4
collision_errors=[]
for mesh in meshes:
    points=np.unique(np.round(np.array(mesh['vertices'])[:,:3],5),axis=0)
    points=points[ConvexHull(points).vertices]
    budget=128 if mesh['name']=='SM_OilBottle' else 64
    # Explicit offline collision LOD, leaving visible geometry untouched. Add the
    # point furthest outside the current convex until the budget/error is met.
    directions=np.random.default_rng(7).normal(size=(16,3))
    chosen=list(set(np.argmax(points@directions.T,axis=0)))
    while len(chosen)<min(budget,len(points)):
        hull=ConvexHull(points[chosen]);dist=(points@hull.equations[:,:3].T+hull.equations[:,3]).max(axis=1)
        ix=int(dist.argmax())
        if dist[ix]<1e-5:break
        assert ix not in chosen;chosen.append(ix)
    hull=ConvexHull(points[chosen]);error=float((points@hull.equations[:,:3].T+hull.equations[:,3]).max())
    mesh['hull']=points[chosen].tolist();collision_errors.append(error)
# Manifold uses right-handed outward triangle winding. UE rasterizes the
# opposite winding. Keep the outward normals/UVs and reverse only triangle order.
for mesh in meshes:
    mesh['triangles']=np.array(mesh['triangles']).reshape(-1,3)[:,[1,0,2]].reshape(-1).tolist()
# Intact rendering retains the source surface/normals. The boolean cavity is
# only for closed fragment baking; its extra wall creates stacked glass contours.
from BottleSource import source_mesh
surface=source_mesh()
for key in ['vertices','triangles','slots']:whole[key]=surface[key]
data={'materials':['/Game/_mygame/OilBottle/Materials/M_OilBottleGlass','/Game/_mygame/OilBottle/Materials/M_OilBottleCork'], 'meshes':meshes}
(out/'geometry.json').write_text(json.dumps(data,separators=(',',':')))
receipt={'source':'https://www.fab.com/listings/adc6b678-4635-4c62-a686-7771d1e8e2ca','source_sha256':hashlib.sha256(b).hexdigest(),
    'author':'mokbulsd','license':'Fab Standard License; user approved Oct24 2026',
    'height_cm':float(cv[:,2].max()),'glass_volume_cm3':glass.volume(),'fragments_volume_cm3':sum(volumes),
    'fragment_count':20,'triangles':[len(x['triangles'])//3 for x in meshes],
    'collision_vertices':[len(x['hull']) for x in meshes],'collision_max_inset_cm':collision_errors,
    'cork_reseated_on_mouth':True}
(out/'bake.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
