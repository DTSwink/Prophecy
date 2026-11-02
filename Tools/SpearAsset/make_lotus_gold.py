"""Author a calibrated, seamless gold microfinish for the lotus pommel only.

This is mathematical PBR-map generation, not an edit to reference imagery or
the accepted spear atlas. The output is an independent material tile. Real
carved panels and lotus petals must be geometry; these maps only supply wear.
"""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import hashlib,json,math,time
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/Diagnostics/ImperialSpear/PommelLotus/Gold'
ATLAS=ROOT/'Exports/ImperialSpear/Textures'
SIZE=2048
PX_PER_MM=12.0
SEED=2710270404
BASE_RGB=(214,178,111)
PREFIX='T_ImperialSpear_LotusGold_'
SCRATCH_HEIGHT_GAIN=1.4

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def periodic_noise(rng,grid):
    """Periodic C1 value noise: quiet coherent wear without cloudy albedo."""
    source=rng.random((grid,grid),dtype=np.float32)*2-1
    q=np.arange(SIZE,dtype=np.float32)*grid/SIZE
    lo=np.floor(q).astype(np.int32);hi=(lo+1)%grid
    t=q-lo;t=t*t*(3-2*t)
    a=source[lo[:,None],lo[None,:]]*(1-t[None,:])+source[lo[:,None],hi[None,:]]*t[None,:]
    b=source[hi[:,None],lo[None,:]]*(1-t[None,:])+source[hi[:,None],hi[None,:]]*t[None,:]
    return (a*(1-t[:,None])+b*t[:,None]).astype(np.float32)

def tiled_polyline(draw,points,fill,width,n):
    xs=[p[0] for p in points];ys=[p[1] for p in points]
    shifts_x=[0]+([n] if min(xs)<0 else [])+([-n] if max(xs)>=n else [])
    shifts_y=[0]+([n] if min(ys)<0 else [])+([-n] if max(ys)>=n else [])
    for ox in shifts_x:
        for oy in shifts_y:
            draw.line([(int(round(x+ox)),int(round(y+oy))) for x,y in points],fill=fill,width=width,joint='curve')

def scratch_layer(rng,count,coarse):
    """Short contact tracks, varied and broken; no closed crack network."""
    ss=2;n=SIZE*ss
    im=Image.new('L',(n,n),0);draw=ImageDraw.Draw(im)
    for _ in range(count):
        x,y=rng.uniform(0,n,2)
        length_mm=float(rng.uniform(.6,4.8) if coarse else rng.uniform(.16,1.4))
        length=length_mm*PX_PER_MM*ss
        # Mostly directionally rubbed marks, with enough crossing scratches
        # to keep the surface from reading as brushed parallel stripes.
        if rng.random()<.58:angle=float(rng.normal(-.4,.52))
        else:angle=float(rng.uniform(-math.pi,math.pi))
        tangent=np.array((math.cos(angle),math.sin(angle)))
        cross=np.array((-tangent[1],tangent[0]))
        bends=4 if coarse else 3
        widths=(1,2,3) if coarse else (1,1,2)
        width=int(rng.choice(widths));strength=int(rng.uniform(95,235) if coarse else rng.uniform(50,200))
        points=[]
        for j in range(bends+1):
            t=j/bends
            bend=float(rng.normal(0,.075))*length*math.sin(math.pi*t)
            p=np.array((x,y))+t*length*tangent+bend*cross
            points.append(tuple(p))
        # Fine tracks have variable, feathered endpoints instead of uniform
        # dark threads. Sparse skipped sections simulate broken contact wear.
        for j in range(bends):
            if coarse and rng.random()<.10:continue
            taper=.55 if j in (0,bends-1) else 1.0
            tiled_polyline(draw,points[j:j+2],int(strength*taper),width,n)
    im=im.resize((SIZE,SIZE),Image.Resampling.LANCZOS)
    # The tiny filter produces subpixel rounded groove shoulders.
    im=im.filter(ImageFilter.GaussianBlur(.22 if coarse else .16))
    return np.asarray(im,dtype=np.float32)/255

def enforce_repeat(array):
    # Same endpoints for interpolation across a texture repeat; the analytic
    # noise and wrapped scratches already agree across the surrounding pixels.
    array[-1]=array[0];array[:,-1]=array[:,0]
    return array

def save(name,array,mode):
    data=np.rint(np.clip(array,0,1)*255).astype(np.uint8)
    enforce_repeat(data)
    path=OUT/(PREFIX+name+'.png')
    Image.fromarray(data,mode).save(path,optimize=True)
    return path

def main():
    started=time.time();OUT.mkdir(parents=True,exist_ok=True)
    protected={p.name:digest(p) for p in sorted(ATLAS.glob('*.png'))}
    rng=np.random.default_rng(SEED)
    macro=periodic_noise(rng,18)
    medium=periodic_noise(rng,91)
    micro=periodic_noise(rng,680)
    coarse=scratch_layer(rng,4200,True)
    fine=scratch_layer(rng,16000,False)
    # Geometry inspection exposed broad specular clouds from even modest
    # 2mm roughness variation. Only discrete scratch depth is strengthened;
    # the quiet fine metal substrate stays at its original amplitude.
    height_mm=(SCRATCH_HEIGHT_GAIN*(-.0080*coarse-.0032*fine)
               +.00065*micro+.00018*medium).astype(np.float32)
    # Shallow displaced metal immediately alongside the deeper incisions.
    mask=Image.fromarray(np.rint(coarse*255).astype(np.uint8),'L')
    shoulder=np.asarray(mask.filter(ImageFilter.MaxFilter(3)),dtype=np.float32)/255
    burr=np.maximum(0,shoulder-coarse)
    height_mm+=.00115*burr
    # Isolated microscopic dings, well below the scale of the actual carving.
    pits=np.clip((-micro-.55)*2.0,0,1)
    height_mm-=.00065*pits
    height_mm=enforce_repeat(height_mm)
    dx=(np.roll(height_mm,-1,axis=1)-np.roll(height_mm,1,axis=1))*(PX_PER_MM*.5)
    # Image rows go down while tangent V goes up.
    dy=-(np.roll(height_mm,-1,axis=0)-np.roll(height_mm,1,axis=0))*(PX_PER_MM*.5)
    nx,ny,nz=-dx,-dy,np.ones_like(dx)
    inv=1/np.sqrt(nx*nx+ny*ny+nz*nz)
    normal=np.stack((nx*inv,ny*inv,nz*inv),axis=2)
    base=np.empty((SIZE,SIZE,3),dtype=np.float32)
    # A restrained, coherent patina signal; linear highlights remain the
    # material/lighting's job, not white streaks baked into the color map.
    color_delta=.0028*medium+.0012*macro+.0008*micro-.032*coarse-.011*fine-.0015*pits
    for channel,value in enumerate(BASE_RGB):
        base[:,:,channel]=value/255+color_delta*(1.0 if channel!=2 else .8)
    broad_roughness=.0008*medium+.0005*macro
    rough=np.clip(.319+broad_roughness+.0035*micro
                  +.052*coarse+.018*fine-.010*burr,.300,.375)
    orm=np.stack((np.ones_like(rough),rough,np.ones_like(rough),np.full_like(rough,.5)),axis=2)
    paths={}
    paths['BaseColor']=save('BaseColor',base,'RGB')
    paths['ORM']=save('ORM',orm,'RGBA')
    paths['NormalGL']=save('NormalGL',normal*.5+.5,'RGB')
    normal[:,:,1]*=-1
    paths['NormalDX']=save('NormalDX',normal*.5+.5,'RGB')
    encoded=np.rint(np.clip((height_mm+.016)/.020,0,1)*65535).astype(np.uint16)
    enforce_repeat(encoded)
    height_path=OUT/(PREFIX+'Height_mm_m016_p004.png')
    Image.fromarray(encoded).save(height_path)
    paths['HeightDiagnostic']=height_path
    assert {p.name:digest(p) for p in sorted(ATLAS.glob('*.png'))}==protected,'Accepted atlas changed'
    seams={}
    for name,path in paths.items():
        data=np.asarray(Image.open(path))
        seams[name]={'horizontal_endpoint_identical':bool(np.array_equal(data[:,0],data[:,-1])),
                     'vertical_endpoint_identical':bool(np.array_equal(data[0],data[-1]))}
        assert all(seams[name].values()),name
    report={'status':'POMMEL_ONLY_PBR_MAPS_GENERATED','revision':'02 — quiet substrate, discrete scratches strengthened',
            'seed':SEED,'size_px':[SIZE,SIZE],
            'pixel_density_px_per_mm':PX_PER_MM,'uv_repeat_physical_size_mm':SIZE/PX_PER_MM,
            'recommended_normal_strength':1.0,'base_color_srgb_bytes':BASE_RGB,
            'base_color_mean_srgb_bytes':(base.mean(axis=(0,1),dtype=np.float64)*255).tolist(),
            'roughness':{'mean':float(rough.mean()),'p05':float(np.percentile(rough,5)),
                         'p95':float(np.percentile(rough,95)),'min':float(rough.min()),'max':float(rough.max())},
            'height_mm':{'min':float(height_mm.min()),'max':float(height_mm.max()),
                         'p01':float(np.percentile(height_mm,1)),'p99':float(np.percentile(height_mm,99))},
            'normal_tilt_degrees':{'p95':float(np.percentile(np.degrees(np.arctan(np.hypot(dx,dy))),95)),
                                   'max':float(np.degrees(np.arctan(np.hypot(dx,dy))).max())},
            'scratch_counts':{'broken_contact_tracks':4200,'fine_hairlines':16000},
            'scratch_height_gain':SCRATCH_HEIGHT_GAIN,
            'broad_roughness_peak_to_peak':float(broad_roughness.max()-broad_roughness.min()),
            'broad_roughness_std':float(broad_roughness.std()),
            'microfinish_only':True,'macro_carvings_must_be_geometry':True,
            'normal_convention':'NormalGL +Y, Blender/glTF; NormalDX green inverted for Unreal',
            'orm_channels':{'R':'AO=1','G':'Roughness','B':'Metallic=1','A':'Specular=0.5; not opacity'},
            'height_diagnostic_encoding_mm':[-.016,.004],
            'existing_atlas_file_hashes_unchanged':protected,'seam_checks':seams,
            'files':{key:{'path':str(path),'sha256':digest(path)} for key,path in paths.items()},
            'generation_seconds':time.time()-started}
    (OUT/'Lotus_Gold_Report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','size_px','roughness','height_mm','normal_tilt_degrees','generation_seconds')},indent=2))

if __name__=='__main__':main()
