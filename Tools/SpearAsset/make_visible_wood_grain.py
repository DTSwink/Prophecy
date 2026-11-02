"""Add readable long growth fibres above the existing subpixel wood texture."""
from pathlib import Path
import json,shutil,hashlib,math
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'Exports/ImperialSpear'; TEX=OUT/'Textures'
BACK=ROOT/'Saved/Diagnostics/ImperialSpear/BeforeVisibleGrain_v1'; BOX=(0,2048,2048,4096)
files=['T_ImperialSpear_BaseColor.png','T_ImperialSpear_NormalGL.png','T_ImperialSpear_NormalDX.png']
if not BACK.exists():
 BACK.mkdir(parents=True)
 for name in files: shutil.copy2(TEX/name,BACK/name)
rng=np.random.default_rng(27102711); n=2048
dark=Image.new('L',(n,n)); light=Image.new('L',(n,n)); dd=ImageDraw.Draw(dark); dl=ImageDraw.Draw(light)
for k in range(50):
 x=(k+.5)*n/50+rng.uniform(-10,10); bend=rng.uniform(4,15); phase=rng.uniform(0,math.tau)
 start=rng.uniform(-700,100); finish=rng.uniform(1700,2800)
 pts=[]
 for j in range(40):
  t=j/39; y=start+(finish-start)*t; px=x+bend*math.sin(t*2.2+phase)+2*math.sin(t*8+phase)
  pts.append((px,y))
 dd.line(pts,fill=int(rng.integers(140,240)),width=int(rng.integers(8,15)))
 dl.line([(x+6,y) for x,y in pts],fill=int(rng.integers(100,190)),width=int(rng.integers(3,7)))
dark=np.asarray(dark.filter(ImageFilter.GaussianBlur(.6)),dtype=np.float32)/255
light=np.asarray(light.filter(ImageFilter.GaussianBlur(.5)),dtype=np.float32)/255
tone=1-dark*.48+light*.28
images={name:Image.open(BACK/name).copy() for name in files}
base=np.array(images[files[0]].crop(BOX)).astype(np.float32)
images[files[0]].paste(Image.fromarray(np.rint(np.clip(base*tone[:,:,None],0,255)).astype(np.uint8)),BOX)
old=(np.asarray(images[files[1]].crop(BOX),dtype=np.float32)-128)/127
height=-dark*.015+light*.006; dy,dx=np.gradient(height,1570/n,100/n)
nx=-dx+old[:,:,0]/np.maximum(.1,old[:,:,2]); ny=dy+old[:,:,1]/np.maximum(.1,old[:,:,2]); inv=1/np.sqrt(nx*nx+ny*ny+1)
gl=np.rint(np.clip(np.stack((nx*inv,ny*inv,inv),-1)*127+128,0,255)).astype(np.uint8)
directx=gl.copy(); directx[:,:,1]=255-directx[:,:,1]
images[files[1]].paste(Image.fromarray(gl),BOX); images[files[2]].paste(Image.fromarray(directx),BOX)
def outside(im):
 h=hashlib.sha256()
 for box in [(0,0,4096,2048),(2048,2048,4096,4096)]: h.update(im.crop(box).tobytes())
 return h.hexdigest()
checks={}
for name,im in images.items():
 before=outside(Image.open(BACK/name)); after=outside(im); assert before==after
 im.save(TEX/name,compress_level=3); checks[name]=after
(OUT/'Visible_Grain_Verification.json').write_text(json.dumps({'major_long_fibres':50,'roughness_and_specular_unchanged':True,'normal_depth_mm':.015,'outside_wood_sha256':checks},indent=2),encoding='utf-8')
print('Long red-brown growth fibres added; all other material pixels unchanged.')
