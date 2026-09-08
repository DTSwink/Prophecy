"""Bake rest-neck-height progress into head UVs; no source/geometry edits."""
import json
import struct
import zlib
from pathlib import Path
import numpy as np

out=Path(__file__).resolve().parents[2]/'Saved/BossShading/20260908/NeckColor'
geometry=json.loads((out/'geometry.json').read_text())
landmarks=json.loads((out/'neck_landmarks.json').read_text())
low=landmarks['neck_base_z_cm']/100
high=landmarks['neck_top_z_cm']/100
assert high>low
size=1024
values=np.ones((size,size),dtype=float)
covered=np.zeros((size,size),dtype=bool)
for world,uv in geometry['triangles']:
    world=np.asarray(world);uv=np.asarray(uv)
    coords=np.column_stack((uv[:,0]*size-.5,(1-uv[:,1])*size-.5))
    lo=np.maximum(np.ceil(coords.min(0)).astype(int),0)
    hi=np.minimum(np.floor(coords.max(0)).astype(int),size-1)
    if np.any(lo>hi):continue
    a,b,c=coords
    denom=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(denom)<1e-10:continue
    yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
    wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/denom
    wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/denom
    wc=1-wa-wb
    inside=(wa>=-1e-8)&(wb>=-1e-8)&(wc>=-1e-8)
    z=wa*world[0,2]+wb*world[1,2]+wc*world[2,2]
    v=values[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
    v[inside]=np.clip((z[inside]-low)/(high-low),0,1)
    covered[lo[1]:hi[1]+1,lo[0]:hi[0]+1]|=inside
# UV gutter expansion, not a blur across the actual neck/face.
valid=covered.copy()
for _ in range(20):
    total=np.zeros_like(values);count=np.zeros_like(values)
    for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
        v=np.roll(valid,(dy,dx),(0,1));c=np.roll(values,(dy,dx),(0,1))
        if dy<0:v[dy:]=False
        if dy>0:v[:dy]=False
        if dx<0:v[:,dx:]=False
        if dx>0:v[:,:dx]=False
        total+=c*v;count+=v
    fill=(~valid)&(count>0)
    values[fill]=total[fill]/count[fill];valid|=fill
encoded=np.rint(values*65535).astype('>u2')
def chunk(t,b):return struct.pack('>I',len(b))+t+b+struct.pack('>I',zlib.crc32(t+b)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,16,0,0,0,0))
png+=chunk(b'IDAT',zlib.compress(b''.join(b'\0'+r.tobytes() for r in encoded),9))+chunk(b'IEND',b'')
(out/'T_Boss_NeckColorProgress.png').write_bytes(png)
report={**landmarks,'full_strength_fraction':.75,'fade_fraction':.25,
        'full_strength_until_z_cm':(low+.75*(high-low))*100,
        'fade_height_cm':.25*(high-low)*100,
        'method':'UV-baked rest height from neck_01 to head; independent of AO surface-distance mask',
        'formula':'original_head_weight=saturate((progress-0.75)/0.25)',
        'source_geometry_and_textures_unchanged':True}
(out/'neck_progress.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
