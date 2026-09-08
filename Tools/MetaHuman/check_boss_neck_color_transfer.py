"""Compare generated head collar texels with correctly wrapped body samples."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

out=Path(__file__).resolve().parents[2]/'Saved/BossShading/20260908/NeckColor'
data=json.loads((out/'geometry.json').read_text())
body=np.asarray(Image.open(out/'T_Body_BC_source.png').convert('RGB'),dtype=float)/255
head=np.asarray(Image.open(out/'T_Boss_NeckBodyColor.png').convert('RGB'),dtype=float)/255
decode=lambda x:np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
body=decode(body);head=decode(head)
def sample(img,uv,wrap=False):
    uv=np.asarray(uv)
    if wrap:uv=uv-np.floor(uv)
    h,w=img.shape[:2]
    x,y=np.clip([uv[0]*w-.5,(1-uv[1])*h-.5],[0,0],[w-1,h-1])
    a,b=int(x),int(y);c,d=min(a+1,w-1),min(b+1,h-1)
    fx,fy=x-a,y-b
    return (img[b,a]*(1-fx)+img[b,c]*fx)*(1-fy)+(img[d,a]*(1-fx)+img[d,c]*fx)*fy
corners={tuple(p):np.asarray(uv) for points,uvs in data['triangles'] for p,uv in zip(points,uvs)}
errors=[];wrong=[]
for a,b,ua,ub in data['segments']:
    ha,hb=corners[tuple(a)],corners[tuple(b)]
    for t in (0,.25,.5,.75,1):
        uv=np.asarray(ua)*(1-t)+np.asarray(ub)*t
        wanted=sample(body,uv,True)
        actual=sample(head,ha*(1-t)+hb*t)
        errors.append(np.abs(actual-wanted))
        wrong.append(np.abs(sample(body,uv)-wanted))
errors=np.asarray(errors);wrong=np.asarray(wrong)
result={'samples':len(errors),'linear_rgb_mean_abs_error':errors.mean(0).tolist(),
        'linear_rgb_max_abs_error':errors.max(0).tolist(),
        'old_clamped_linear_rgb_mean_abs_error':wrong.mean(0).tolist(),
        'new_mean_error':float(errors.mean()),'old_mean_error':float(wrong.mean()),
        'check':'Offline UV/color transfer; not a final rendered or user visual acceptance'}
assert errors.mean()<wrong.mean()*.25,result
(out/'wrapped_transfer_check.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
