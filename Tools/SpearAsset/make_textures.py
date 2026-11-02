"""Deterministic, authored PBR atlas. No external texture sources."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Exports/ImperialSpear/Textures'
OUT.mkdir(parents=True,exist_ok=True)
N=4096
rng=np.random.default_rng(271027)
base=Image.new('RGB',(N,N))
orm=Image.new('RGB',(N,N),(255,120,0))
normal=Image.new('RGB',(N,N),(128,128,255))
# Pixel bounds, in top-down image convention (UV v points up).
regions={'steel':(0,0,2048,2048),'gold':(2048,0,4096,2048),
         'wood':(0,2048,2048,4096),'leather':(2048,2048,3072,4096),
         'silk':(3072,2048,4096,4096)}
for kind,box in regions.items():
    x0,y0,x1,y1=box; w=x1-x0; h=y1-y0
    u=np.linspace(0,1,w,dtype=np.float32)[None,:]
    v=np.linspace(0,1,h,dtype=np.float32)[:,None]
    fine=rng.normal(0,1,(h,w)).astype(np.float32)
    small=Image.fromarray(rng.integers(0,256,(64,64),dtype=np.uint8),'L').resize((w,h),Image.Resampling.BICUBIC)
    cloud=np.array(small,dtype=np.float32)/255-.5
    relief=np.zeros((h,w),dtype=np.float32)
    if kind=='steel':
        brush=np.sin(u*1800+np.sin(v*13)*.6)*.7+fine*.5
        tone=1+cloud*.025+brush*.004
        color=np.array([166,175,184]); rough=.32+cloud*.035+fine*.003
        relief=brush*.0007+cloud*.008
        metal=1
    elif kind=='gold':
        # Thin incised repeating chevrons and small quatrefoils, restrained patina.
        a=np.mod(u*12+v*16,1); b=np.mod(u*12-v*16,1)
        engrave=np.exp(-np.minimum(a,1-a)**2/.0012)+np.exp(-np.minimum(b,1-b)**2/.0012)
        mask=Image.fromarray(np.uint8(np.clip(engrave*.5,0,1)*255))
        engraved=np.array(mask,dtype=np.float32)/255
        tone=1+cloud*.035+fine*.003-engraved*.08
        color=np.array([164,115,44]); rough=.37+cloud*.025+engraved*.04
        relief=cloud*.003-engraved*.018+fine*.0005
        metal=1
    elif kind=='wood':
        phase=u*440+np.sin(v*9+u*12)*1.8+np.sin(v*31+u*23)*.55
        grain=np.sin(phase)+.38*np.sin(phase*2.12)+.2*np.sin(phase*4.3)
        pores=np.clip(np.sin(phase*3)-.92,0,1)
        tone=1+grain*.105+cloud*.12+fine*.012-pores*.35
        color=np.array([43,17,14]); rough=.48+grain*.015+cloud*.04
        relief=grain*.003-pores*.012+fine*.0006
        metal=0
    elif kind=='leather':
        # Fine pore field. Raised wrap edges belong to geometry.
        pores=np.maximum(fine-1.2,0)
        tone=1+cloud*.11+fine*.018-pores*.018
        color=np.array([50,17,16]); rough=.62+cloud*.04+fine*.003
        relief=cloud*.005+fine*.0013-pores*.004
        metal=0
    else:
        thread=(np.sin(u*1500)*.6+np.sin(u*3100)*.3)*(1+.15*np.sin(v*32))
        weave=np.sin(v*2300)*.15
        tone=1+thread*.12+cloud*.07+fine*.012
        color=np.array([95,8,15]); rough=.58+thread*.015+cloud*.025
        relief=thread*.003+weave*.0008
        metal=0
    rgb=np.uint8(np.clip(tone[:,:,None]*color[None,None,:],0,255))
    # Normal amplitude deliberately tiny; no stone-like noise on metal.
    gy,gx=np.gradient(relief)
    strength=2.5 if kind in ['steel','gold'] else 6
    nx=-gx*strength; ny=gy*strength
    nz=np.ones_like(nx); length=np.sqrt(nx*nx+ny*ny+1)
    normals=np.uint8(np.clip(np.stack((nx/length,ny/length,nz/length),axis=-1)*127.5+127.5,0,255))
    packed=np.empty_like(rgb); packed[:,:,0]=255
    packed[:,:,1]=np.uint8(np.clip(rough,0,1)*255); packed[:,:,2]=255*metal
    base.paste(Image.fromarray(rgb),box)
    orm.paste(Image.fromarray(packed),box)
    normal.paste(Image.fromarray(normals),box)
    print(kind,flush=True)
base.save(OUT/'T_ImperialSpear_BaseColor.png',compress_level=3)
orm.save(OUT/'T_ImperialSpear_ORM.png',compress_level=3)
normal.save(OUT/'T_ImperialSpear_NormalGL.png',compress_level=3)
# DirectX tangent normal for Unreal; OpenGL version remains for Blender/glTF.
arr=np.array(normal); arr[:,:,1]=255-arr[:,:,1]
Image.fromarray(arr).save(OUT/'T_ImperialSpear_NormalDX.png',compress_level=3)
print('Atlas complete: 4096px, BaseColor + ORM + tangent normals')
