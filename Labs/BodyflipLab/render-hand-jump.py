import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
folder=Path('Saved/BodyflipLab/HandJump')
data=json.loads((folder/'mesh-index.json').read_text()); meshes=np.memmap(folder/'meshes.bin',dtype=np.float32,mode='r')
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',15)
prefix=sys.argv[1] if len(sys.argv)>1 else 'floor'
# A fixed orthographic audit camera, framed around the whole short sequence.
mins=np.full(3,np.inf);maxs=-mins.copy()
for item in data['index']:
    ps=meshes[item['offset']//4:item['offset']//4+item['count']].reshape(-1,9)[:,:3]
    mins=np.minimum(mins,ps.min(axis=0));maxs=np.maximum(maxs,ps.max(axis=0))
center=(mins+maxs)/2; extent=max(2.3,np.linalg.norm(maxs-mins)*.9)
def render(i,view=(4,1.6,5),size=(270,300),close=False):
    item=data['index'][i]; a=meshes[item['offset']//4:item['offset']//4+item['count']].reshape(-1,9)
    center=np.array(item['root'])+[0,1.15,0];extent=3.4
    if close: center=np.array(item['root'])+[0,.75,0];extent=1.8
    towards=np.array(view,dtype=float);towards/=np.linalg.norm(towards);right=np.cross([0,1,0],towards);right/=np.linalg.norm(right);up=np.cross(towards,right)
    local=a[:,:3]-center;xy=np.stack((local@right,-local@up),axis=1)*min(size)/extent;xy+=[size[0]/2,size[1]*.52]
    depth=(local@towards).reshape(-1,3).mean(axis=1);tris=xy.reshape(-1,3,2); light=np.array([-.35,.85,.4]);light/=np.linalg.norm(light)
    shade=.4+.6*np.maximum(0,a[:,3:6]@light);rgb=np.clip(a[:,6:9]*shade[:,None]*255,0,255).reshape(-1,3,3).mean(axis=1).astype(np.uint8)
    im=Image.new('RGB',size,'#141b26');d=ImageDraw.Draw(im)
    def project(p):
        q=np.array(p)-center;return tuple(np.array([q@right,-q@up])*min(size)/extent+[size[0]/2,size[1]*.52])
    for z in np.arange(-1,1.01,.25):
        d.line([project([z,0,-1]),project([z,0,1])],fill='#293a51')
        d.line([project([-1,0,z]),project([1,0,z])],fill='#293a51')
    sf=data['surface'];origin=np.array(sf['origin']);u=np.array(sf['u']);v=np.array(sf['v'])
    for k in np.arange(-1,1.01,.25):
        d.line([project(origin+k*u-v),project(origin+k*u+v)],fill='#48566e')
        d.line([project(origin+k*v-u),project(origin+k*v+u)],fill='#48566e')
    for j in np.argsort(depth): d.polygon([tuple(p) for p in tris[j]],fill=tuple(rgb[j]))
    d.text((8,7),f"F{item['frame']} · {item['phase']}",font=font,fill='white');return im
w,h=270,300
if '--contact-only' not in sys.argv:
    chosen=list(range(0,len(data['index']),3))
    sheet=Image.new('RGB',(w*6,h*((len(chosen)+5)//6)),'#0c121c')
    for n,i in enumerate(chosen):sheet.paste(render(i),(n%6*w,n//6*h))
    sheet.save(folder/(prefix+'-frames.png'))
    frames=[render(i,size=(450,450)) for i in range(len(data['index']))]
    frames[0].save(folder/(prefix+'-motion.gif'),save_all=True,append_images=frames[1:],duration=33,loop=0)
contact=min(range(len(data['index'])),key=lambda i:abs(data['index'][i]['time']-data['timing']['contact']))
sheet=Image.new('RGB',(w*5,h*2),'#0c121c')
for n,i in enumerate(range(max(0,contact-4),min(len(data['index']),contact+6))):sheet.paste(render(i,view=(6,1.5,1),close=True),(n%5*w,n//5*h))
sheet.save(folder/(prefix+'-contact.png'));print('Saved collider frames/contact/motion')
