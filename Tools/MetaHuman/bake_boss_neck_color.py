"""Extend the body's actual collar colors into head UVs; preserve source assets.

Run with normal Python. A read-only background Blender pass extracts geometry;
the PNG is sampled/interpolated in linear RGB and written as an sRGB color map.
"""
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
OUT = PROJECT / 'Saved/BossShading/20260908/NeckColor'
SOURCE = Path(r'C:/Users/singerie/Documents/Blender/bossfinalsave.blend')

def geometry():
    import bpy
    import hashlib
    obj = bpy.data.objects['boss']
    mesh = obj.data
    uv = mesh.uv_layers[0]
    mesh.calc_loop_triangles()
    pairs = json.loads((PROJECT/'Saved/BossSeamAudit/20260908/collar_normals_candidate.json').read_text())['boundary_pair_indices']
    body_edges = {}
    for p in mesh.polygons:
        if p.material_index != 7:
            continue
        coords = {mesh.loops[i].vertex_index: list(uv.data[i].uv) for i in p.loop_indices}
        for edge in p.edge_keys:
            body_edges[tuple(sorted(edge))] = coords
    segments = []
    for (ba,ha),(bb,hb) in zip(pairs,pairs[1:]+pairs[:1]):
        edge = body_edges[tuple(sorted((ba,bb)))]
        segments.append([list(obj.matrix_world@mesh.vertices[ha].co),list(obj.matrix_world@mesh.vertices[hb].co),edge[ba],edge[bb]])
    triangles = [[ [list(obj.matrix_world@mesh.vertices[v].co) for v in t.vertices],
                   [list(uv.data[i].uv) for i in t.loops]]
                 for t in mesh.loop_triangles if mesh.polygons[t.polygon_index].material_index == 6]
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'geometry.json').write_text(json.dumps({'segments':segments,'triangles':triangles,
        'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}))
    print('READ_ONLY_COLLAR_COLOR_GEOMETRY_EXPORTED')

def bake():
    import subprocess
    import numpy as np
    from PIL import Image
    if '--cached-geometry' not in sys.argv:
        subprocess.run([r'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe',
                        '--background',str(SOURCE),'--python',str(Path(__file__).resolve()),'--','--geometry'],check=True)
    data=json.loads((OUT/'geometry.json').read_text())
    import hashlib
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==data['source_sha256'], 'Geometry cache no longer matches source'
    size=1024
    points=np.zeros((size,size,3),np.float64)
    covered=np.zeros((size,size),bool)
    for world,uv in data['triangles']:
        uv=np.asarray(uv); world=np.asarray(world)
        coords=np.column_stack((uv[:,0]*size-.5,(1-uv[:,1])*size-.5))
        lo=np.maximum(np.ceil(coords.min(0)).astype(int),0)
        hi=np.minimum(np.floor(coords.max(0)).astype(int),size-1)
        if np.any(lo>hi): continue
        a,b,c=coords
        denom=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(denom)<1e-10: continue
        yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        wa=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/denom
        wb=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/denom
        wc=1-wa-wb
        inside=(wa>=-1e-8)&(wb>=-1e-8)&(wc>=-1e-8)
        region=points[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        world_grid=wa[...,None]*world[0]+wb[...,None]*world[1]+wc[...,None]*world[2]
        region[inside]=world_grid[inside]
        covered[lo[1]:hi[1]+1,lo[0]:hi[0]+1]|=inside
    p=points[covered]
    best=np.full(len(p),np.inf)
    mapped=np.zeros((len(p),2))
    for a,b,uva,uvb in data['segments']:
        a=np.asarray(a); b=np.asarray(b); delta=b-a
        t=np.clip(((p-a)*delta).sum(1)/(delta@delta),0,1)
        d=((p-(a+t[:,None]*delta))**2).sum(1)
        take=d<best
        mapped[take]=np.asarray(uva)+(np.asarray(uvb)-uva)*t[take,None]
        best[take]=d[take]
    body=np.asarray(Image.open(OUT/'T_Body_BC_source.png').convert('RGB'),np.float64)/255.
    body=np.where(body<=.04045,body/12.92,((body+.055)/1.055)**2.4)
    height,width=body.shape[:2]
    # The Boss body UVs occupy tile U=[1,2]; UE's source texture wraps.
    # Clamping those coordinates to [0,1] samples its rightmost background,
    # not the body's collar. Wrap only after interpolating each source edge.
    source_uv_range=[mapped.min(0).tolist(),mapped.max(0).tolist()]
    mapped=mapped-np.floor(mapped)
    assert np.all((mapped>=0)&(mapped<1))
    px=np.clip(mapped[:,0]*width-.5,0,width-1)
    py=np.clip((1-mapped[:,1])*height-.5,0,height-1)
    x0=px.astype(int);y0=py.astype(int);x1=np.minimum(x0+1,width-1);y1=np.minimum(y0+1,height-1)
    fx=(px-x0)[:,None];fy=(py-y0)[:,None]
    color=(body[y0,x0]*(1-fx)+body[y0,x1]*fx)*(1-fy)+(body[y1,x0]*(1-fx)+body[y1,x1]*fx)*fy
    image=np.zeros((size,size,3));image[covered]=color
    # Padded UV gutters for filtering. Each iteration expands only from known pixels.
    valid=covered.copy()
    for _ in range(20):
        total=np.zeros_like(image);count=np.zeros((size,size))
        for dy,dx in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
            v=np.roll(valid,(dy,dx),(0,1)); col=np.roll(image,(dy,dx),(0,1))
            if dy<0:v[dy:]=False
            if dy>0:v[:dy]=False
            if dx<0:v[:,dx:]=False
            if dx>0:v[:,:dx]=False
            total+=col*v[...,None];count+=v
        fill=(~valid)&(count>0)
        image[fill]=total[fill]/count[fill,None]
        valid|=fill
    srgb=np.where(image<=.0031308,image*12.92,1.055*np.maximum(image,0)**(1/2.4)-.055)
    dest=OUT/'T_Boss_NeckBodyColor.png'
    Image.fromarray(np.uint8(np.rint(np.clip(srgb,0,1)*255))).save(dest)
    report={'output':str(dest),'body_source_texture':'/Game/_mygame/MetaHumans/boss/Body/Baked/T_Body_BC_VT',
            'method':'Closest head collar segment mapped to corresponding body edge UV; body texture sampled in linear RGB',
            'segments':len(data['segments']),'resolution':size,'covered_texels':int(covered.sum()),
            'source_sha256':data['source_sha256'],'source_mesh_unchanged':True,
            'source_uv_range_before_wrap':source_uv_range,
            'source_addressing':'Wrap: fract(interpolated body UV), matching UE source texture',
            'body_edge_linear_rgb_min':color.min(0).tolist(),'body_edge_linear_rgb_max':color.max(0).tolist(),
            'visual_validation':'User will check; no visual acceptance claimed'}
    (OUT/'color_transfer.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

if __name__=='__main__':
    geometry() if '--geometry' in sys.argv else bake()
