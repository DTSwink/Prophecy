"""Diffuse collar color DIFFERENCES over the surface; never extrude texture strips.

Works only on cached export geometry and new generated texture data. The source
mesh, UVs and source head/body textures are untouched. Two virtual subdivisions
increase sampling accuracy; no tessellated mesh is exported to Unreal.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.sparse.linalg import spsolve

out=Path(__file__).resolve().parents[2]/'Saved/BossShading/20260908/NeckColor'
data=json.loads((out/'geometry.json').read_text())
decode=lambda x:np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
encode=lambda x:np.where(x<=.0031308,x*12.92,1.055*np.maximum(x,0)**(1/2.4)-.055)
body=decode(np.asarray(Image.open(out/'T_Body_BC_source.png').convert('RGB'),float)/255)
head=decode(np.asarray(Image.open(out/'T_Head_LOD3_BC_original.png').convert('RGB'),float)/255)
def sample(img,uv):
    uv=np.asarray(uv)%1
    h,w=img.shape[:2];xy=uv*np.array([w,-h])+np.array([-.5,h-.5])
    ij=np.floor(xy).astype(int);f=xy-ij
    x,y=ij[...,0]%w,ij[...,1]%h;xx=(x+1)%w;yy=(y+1)%h
    fx,fy=f[...,0,None],f[...,1,None]
    return (img[y,x]*(1-fx)+img[y,xx]*fx)*(1-fy)+(img[yy,x]*(1-fx)+img[yy,xx]*fx)*fy
points=[];lookup={};faces=[];uvs=[];point_uv={}
def vertex(p):
    key=tuple(np.round(p,9))
    if key not in lookup:lookup[key]=len(points);points.append(np.asarray(p))
    return lookup[key]
for world,uv in data['triangles']:
    ids=[vertex(p) for p in world];faces.append(ids);uvs.append(uv)
    for i,u in zip(ids,uv):point_uv[i]=np.asarray(u)
segments=[]
for a,b,ua,ub in data['segments']:
    ia,ib=vertex(a),vertex(b)
    segments.append((ia,ib,np.asarray(ua),np.asarray(ub),point_uv[ia],point_uv[ib]))
boundary={}
for _ in range(2):
    mids={}
    def midpoint(a,b):
        key=tuple(sorted((a,b)))
        if key not in mids:mids[key]=len(points);points.append((points[a]+points[b])*.5)
        return mids[key]
    new_faces=[];new_uv=[]
    for (a,b,c),uv in zip(faces,uvs):
        ab,bc,ca=midpoint(a,b),midpoint(b,c),midpoint(c,a)
        u,v,w=np.asarray(uv);uvab=(u+v)*.5;uvbc=(v+w)*.5;uvca=(w+u)*.5
        new_faces.extend([(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)])
        new_uv.extend([(u,uvab,uvca),(uvab,v,uvbc),(uvca,uvbc,w),(uvab,uvbc,uvca)])
    new_segments=[]
    for a,b,ua,ub,ha,hb in segments:
        m=midpoint(a,b);um=(ua+ub)*.5;hm=(ha+hb)*.5
        new_segments.extend([(a,m,ua,um,ha,hm),(m,b,um,ub,hm,hb)])
    faces,uvs,segments=new_faces,new_uv,new_segments
points=np.asarray(points);faces=np.asarray(faces);uvs=np.asarray(uvs)
for a,b,ua,ub,ha,hb in segments:
    boundary[a]=sample(body,ua)-sample(head,ha)
    boundary[b]=sample(body,ub)-sample(head,hb)
edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
a,b=edges.T;length=np.linalg.norm(points[a]-points[b],axis=1)
assert length.min()>1e-10
rows=np.r_[a,b];cols=np.r_[b,a]
graph=coo_matrix((np.r_[length,length],(rows,cols)),shape=(len(points),len(points))).tocsr()
distance=dijkstra(graph,indices=list(boundary),min_only=True)
# Zero correction past the existing 5.2cm band. Positive graph conductances
# give a harmonic extension without nearest-segment wedges or overshoots.
weights=1/length
W=coo_matrix((np.r_[weights,weights],(rows,cols)),shape=graph.shape).tocsr()
L=coo_matrix((np.asarray(W.sum(axis=1)).ravel(),(np.arange(len(points)),np.arange(len(points)))),shape=graph.shape).tocsr()-W
fixed=(distance>=.052)
fixed[list(boundary)]=True
delta=np.zeros((len(points),3))
for i,d in boundary.items():delta[i]=d
free=np.flatnonzero(~fixed);known=np.flatnonzero(fixed)
delta[free]=spsolve(L[free][:,free],-L[free][:,known]@delta[known])
residual=float(np.abs((L@delta)[free]).max())
assert residual<1e-8
size=head.shape[0];assert head.shape[:2]==(size,size)
field=np.zeros_like(head);covered=np.zeros((size,size),bool)
for ids,uv in zip(faces,uvs):
    if np.max(np.abs(delta[ids]))<1e-12:continue
    coords=np.column_stack((uv[:,0]*size-.5,(1-uv[:,1])*size-.5))
    lo=np.maximum(np.ceil(coords.min(0)).astype(int),0);hi=np.minimum(np.floor(coords.max(0)).astype(int),size-1)
    if np.any(lo>hi):continue
    a,b,c=coords;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(den)<1e-12:continue
    yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
    wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
    wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;wc=1-wa-wb
    inside=(wa>=-1e-8)&(wb>=-1e-8)&(wc>=-1e-8)
    v=field[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
    d=wa[...,None]*delta[ids[0]]+wb[...,None]*delta[ids[1]]+wc[...,None]*delta[ids[2]]
    v[inside]=d[inside];covered[lo[1]:hi[1]+1,lo[0]:hi[0]+1]|=inside
# Fill only the outer UV gutters, not the zero-correction interior face.
head_coverage=np.asarray(Image.open(out.parent/'NeckFade/T_Boss_NeckDistance.png'),float)<65535
valid=covered.copy()
for _ in range(12):
    total=np.zeros_like(field);count=np.zeros(field.shape[:2])
    for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
        v=np.roll(valid,(dy,dx),(0,1));d=np.roll(field,(dy,dx),(0,1))
        if dy<0:v[dy:]=False
        if dy>0:v[:dy]=False
        if dx<0:v[:,dx:]=False
        if dx>0:v[:,:dx]=False
        total+=d*v[...,None];count+=v
    fill=(~valid)&(count>0)&(~head_coverage)
    field[fill]=total[fill]/count[fill,None];valid|=fill
corrected=np.clip(head+field,0,1)
pixels=np.uint8(np.rint(np.clip(encode(corrected),0,1)*255))
Image.fromarray(pixels).save(out/'T_Boss_NeckColorMatched.png')
actual=decode(pixels/255.)
errors=[]
for a,b,ua,ub,ha,hb in segments:
    errors.append(np.abs(sample(actual,ha)-sample(body,ua)))
errors=np.asarray(errors)
report={'method':'Original head color plus harmonic surface correction of body-minus-head collar colors',
        'virtual_vertices':len(points),'virtual_triangles':len(faces),'boundary_samples':len(boundary),
        'harmonic_residual':residual,'mean_boundary_linear_rgb_error':float(errors.mean()),
        'max_boundary_linear_rgb_error':float(errors.max()),'corrected_texels':int(covered.sum()),
        'source_head_texture_preserved_under_additive_field':True,'mesh_and_source_textures_unchanged':True,
        'visual_acceptance':'User must check faint streaks; numerical checks are not visual proof'}
assert errors.mean()<.01,report
(out/'color_diffusion.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
