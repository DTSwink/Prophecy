"""Revision02: controlled metal finishes and a dedicated burgundy lacquer region."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'Exports/ImperialSpear/Textures'
N=4096; rng=np.random.default_rng(271027)
base=Image.new('RGB',(N,N)); orm=Image.new('RGB',(N,N),(255,128,0)); normal=Image.new('RGB',(N,N),(128,128,255))
regions={'steel':(0,0,1024,2048),'edge':(1024,0,1536,2048),'ridge':(1536,0,1792,2048),'steel_shadow':(1792,0,2048,2048),
         'gold':(2048,0,3072,2048),'gold_shadow':(3072,0,3328,2048),'lacquer':(3328,0,3584,2048),'gold_etched':(3584,0,4096,2048),
         'wood':(0,2048,2048,4096),'leather':(2048,2048,3072,4096),'silk':(3072,2048,4096,4096)}
for kind,box in regions.items():
    x0,y0,x1,y1=box; w=x1-x0; h=y1-y0
    u=np.linspace(0,1,w,dtype=np.float32)[None,:]; v=np.linspace(0,1,h,dtype=np.float32)[:,None]
    fine=rng.normal(0,1,(h,w)).astype(np.float32)
    cloud=np.array(Image.fromarray(rng.integers(0,256,(96,48),dtype=np.uint8),'L').resize((w,h),Image.Resampling.BICUBIC),dtype=np.float32)/255-.5
    relief=np.zeros((h,w),dtype=np.float32); metal=1; tone=1+cloud*.025+fine*.002; rough=.33+cloud*.025
    if kind in ['steel','edge','ridge','steel_shadow']:
        color={'steel':[143,153,163],'edge':[207,216,225],'ridge':[191,202,212],'steel_shadow':[52,61,70]}[kind]
        rough={'steel':.38,'edge':.20,'ridge':.23,'steel_shadow':.42}[kind]+cloud*.015+fine*.002
        tone=1+cloud*.015+fine*.003
        relief=np.zeros((h,w),dtype=np.float32)
    elif kind in ['gold','gold_shadow','gold_etched']:
        color=[173,128,59] if kind!='gold_shadow' else [62,38,14]
        rough=(.33 if kind!='gold_shadow' else .47)+cloud*.035
        if kind=='gold_etched':
            # Alternating leaf/ogee cuts, designed along the socket rather than noise.
            phase=u*6
            stripe=np.abs(np.mod(v*8+.18*np.sin(phase*2*np.pi),1)-.5)
            groove=np.exp(-(stripe/.035)**2)
            leaf=np.abs(np.sin(u*np.pi*6))*(.5+.5*np.cos(v*np.pi*16))
            cut=np.clip(groove+.35*np.exp(-((leaf-.62)/.035)**2),0,1)
            tone-=cut*.27; rough+=cut*.10; relief=-cut*.010
        relief+=fine*.000025
    elif kind=='lacquer':
        color=[68,8,11]; rough=.285+cloud*.008; tone=1+cloud*.035+fine*.001; metal=0
    elif kind=='wood':
        phase=u*440+np.sin(v*9+u*12)*1.8+np.sin(v*31+u*23)*.55
        grain=np.sin(phase)+.38*np.sin(phase*2.12)+.2*np.sin(phase*4.3)
        pores=np.clip(np.sin(phase*3)-.92,0,1)
        tone=1+grain*.105+cloud*.12+fine*.012-pores*.35
        color=[43,17,14]; rough=.48+grain*.015+cloud*.04
        relief=grain*.003-pores*.012+fine*.0006; metal=0
    elif kind=='leather':
        pores=np.maximum(fine-1.2,0)
        tone=1+cloud*.11+fine*.018-pores*.018; color=[50,17,16]
        rough=.62+cloud*.04+fine*.003; relief=cloud*.005+fine*.0013-pores*.004; metal=0
    else:
        thread=(np.sin(u*1500)*.6+np.sin(u*3100)*.3)*(1+.15*np.sin(v*32))
        tone=1+thread*.12+cloud*.07+fine*.012; color=[95,8,15]
        rough=.58+thread*.015+cloud*.025; relief=thread*.003+np.sin(v*2300)*.00012; metal=0
    rgb=np.uint8(np.clip(tone[:,:,None]*np.array(color)[None,None,:],0,255))
    gy,gx=np.gradient(relief); strength=3 if kind in ['gold_etched','wood','leather','silk'] else 1
    nx=-gx*strength; ny=gy*strength; length=np.sqrt(nx*nx+ny*ny+1)
    normals=np.uint8(np.clip(np.rint(np.stack((nx/length,ny/length,1/length),axis=-1)*127.5+127.5),0,255))
    packed=np.empty_like(rgb); packed[:,:,0]=255; packed[:,:,1]=np.uint8(np.clip(rough,0,1)*255); packed[:,:,2]=255*metal
    base.paste(Image.fromarray(rgb),box); orm.paste(Image.fromarray(packed),box); normal.paste(Image.fromarray(normals),box)
base.save(OUT/'T_ImperialSpear_BaseColor.png',compress_level=3)
orm.save(OUT/'T_ImperialSpear_ORM.png',compress_level=3)
normal.save(OUT/'T_ImperialSpear_NormalGL.png',compress_level=3)
arr=np.array(normal); arr[:,:,1]=255-arr[:,:,1]
Image.fromarray(arr).save(OUT/'T_ImperialSpear_NormalDX.png',compress_level=3)
print('Revision02 atlas generated: separate forged faces, polished edges, recesses and red lacquer.')
