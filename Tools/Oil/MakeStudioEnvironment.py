"""Small deterministic studio radiance environment; no downloaded HDR dependency."""
from pathlib import Path
import numpy as np
w,h=512,256
y,x=np.mgrid[0:h,0:w];az=(x+.5)/w*2*np.pi-np.pi;el=np.pi/2-(y+.5)/h*np.pi
rgb=np.zeros((h,w,3),np.float32)+.12
def card(a,aw,power):
 d=np.abs(np.arctan2(np.sin(az-a),np.cos(az-a)))
 mask=np.clip((aw-d)/.22,0,1)*np.clip((1.15-np.abs(el))/.18,0,1)
 rgb[:]+=mask[...,None]*power
card(1.45,.57,1.2);card(2.70,.57,1.2)
# Gentle ceiling fill without a hard horizon band.
rgb[:]+=(.22*np.maximum(0,np.sin(el))**4)[...,None]
m=rgb.max(2);mant,exp=np.frexp(m);sc=mant*256/np.maximum(m,1e-9)
rgbe=np.concatenate([np.clip(rgb*sc[...,None],0,255).astype('uint8'),(exp+128).astype('uint8')[...,None]],2)
p=Path(__file__).with_name('Source')/'OilStudio.hdr';p.write_bytes(b'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 256 +X 512\n'+rgbe.tobytes())
print(p)


