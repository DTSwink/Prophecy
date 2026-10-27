"""Reuse cached sword and original CC0 bomb geometry without touching Unreal."""
import base64, hashlib, json
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]

def mesh(name,points,triangles,colors,collision,mass,source):
    hull=ConvexHull(collision)
    return dict(name=name,vertices=np.round(points,8).tolist(),triangles=triangles.flatten().tolist(),
                colors=colors.tolist(),collision=np.round(collision[hull.vertices],8).tolist(),mass=mass,source=source)

sword_path=ROOT.parent/'BodyflipLab/data/sword.json'
s=json.loads(sword_path.read_text(encoding='utf-8'))
v=np.frombuffer(base64.b64decode(s['vertices_b64']),dtype='<f4').reshape(-1,3)
t=np.frombuffer(base64.b64decode(s['triangles_b64']),dtype='<i4').reshape(-1,3)
mask=np.frombuffer(base64.b64decode(s['blade_mask_b64']),dtype=np.uint8)
m=np.array(s['local_to_hand']).reshape(4,4).T
v=v@m[:3,:3].T+m[:3,3]
# Right/left hand anatomical forward and palm signs differ. A proper 180-degree
# rotation about local Z transfers the existing grip to the left, without mirroring.
v=v*np.array([-1,-1,1])
colors=np.array([[.86,.93,.98] if mask[tri].any() else [.52,.24,.07] for tri in t])
sword=mesh('Spear (sword placeholder)',v,t,colors,v,1.2,
    dict(file=str(sword_path),sha256=hashlib.sha256(sword_path.read_bytes()).hexdigest(),hand='hand_l',grip='Original right grip rotated 180 degrees about local Z'))
# Re-express the cached hand-local geometry around the weapon grip. This rigid
# change of basis preserves its original default world pose, while editor axes
# follow the sword (Z toward its blade) rather than the forearm/hand frame.
_,axes=np.linalg.eigh(np.cov(v.T));z=axes[:,-1]
z*=np.sign(v[np.linalg.norm(v,axis=1).argmax()]@z)
x=np.array([1.,0,0]);x-=z*(x@z);x/=np.linalg.norm(x)
basis=np.column_stack([x,np.cross(z,x),z]);pivot=m[:3,3]*[-1,-1,1]
for field in ['vertices','collision']:
    sword[field]=np.round((np.array(sword[field])-pivot)@basis,10).tolist()
sword['bind']=dict(position=pivot.tolist(),rotation=Rotation.from_matrix(basis).as_quat().tolist())
sword['longAxis']=[0,0,1]

bomb_path=PROJECT/'Tools/BombFuse/Geometry.json'
b=json.loads(bomb_path.read_text(encoding='utf-8'));whole=b['meshes'][0]
raw=np.array(whole['vertices']);t=np.array(whole['triangles']).reshape(-1,3)
# Original mesh centre from PrepareGeometry.py, cm to metres; Y-up display.
center=np.array([-1.0239047,0,-1.2153458])
v=(raw[:,:3]-center)[:,[0,2,1]]*.01+np.array([.073,.078,0])
t=t[:,[0,2,1]] # Y/Z conversion reverses handedness.
colors=np.array([[.67,.43,.19] if (raw[tri,12]>0).any() else [.15,.18,.23] for tri in t])
bomb=mesh('Bomb',v,t,colors,v[raw[:,12]==0],.6,
    dict(file=str(bomb_path),asset=b['source'],sha256=hashlib.sha256(bomb_path.read_bytes()).hexdigest(),hand='hand_l',collision='Convex shell; decorative static fuse'))
cache=ROOT/'data/objects.json'
objects=json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else {}
objects.update(sword=sword,bomb=bomb)
cache.write_text(json.dumps(objects,separators=(',',':')),encoding='utf-8')
print(json.dumps({key:dict(vertices=len(x['vertices']),triangles=len(x['triangles'])//3,hullPoints=len(x['collision'])) for key,x in dict(sword=sword,bomb=bomb).items()},indent=2))
