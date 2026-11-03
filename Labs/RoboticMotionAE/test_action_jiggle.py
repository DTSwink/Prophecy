import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import torch,json
from action_jiggle import gates,penalty,SPEC
torch.set_num_threads(1)
T=64;t=torch.arange(T,dtype=torch.float32);mask=torch.ones(T,2,3,dtype=torch.bool);done=torch.zeros(T,2,dtype=torch.long)
def expand(x):return x[:,None,None].expand(T,2,3).clone()
cases={'constant':expand(t*0+.3),'ramp':expand(t*.02),'smooth_stroke':expand(torch.sin(t*2*torch.pi/60)), '2hz_stroke':expand(torch.sin(t*2*torch.pi/15)), 'single_impact':expand((t==30).float()),'tiny_chatter':expand((-1.)**t*.005),'alternating':expand((-1.)**t*.2),'5hz':expand(torch.sin(t*2*torch.pi/6)*.3)}
report={}
for name,x in cases.items():
 g=gates(x,done,mask);loss=penalty(x.roll(1,0),x,x.roll(-1,0),g)
 report[name]={'detected':int(g.sum()),'loss':float(loss)}
 if name in ('alternating','5hz'):assert loss>0 and g.any()
 else:assert loss==0 and not g.any(),name
x=cases['alternating'];g=gates(x,done,mask);assert not g[:6].any() and not g[-6:].any()
done[30]=1;g=gates(x,done,mask);assert not g[25:37].any()
mask[:,:,1]=False;g=gates(x,done,mask);assert not g[:,:,1].any()
# Direct actor gradient exists, reduces oscillations, and cannot affect masked outputs.
x=x.clone().requires_grad_();g=gates(x.detach(),done,mask)
before=penalty(x.roll(1,0),x,x.roll(-1,0),g);before.backward();assert x.grad[:,:,1].abs().sum()==0
with torch.no_grad():y=x-.5*x.grad
after=penalty(y.roll(1,0),y,y.roll(-1,0),g);assert after<before
print(json.dumps(dict(passed=True,cases=report,gradient_before=float(before.detach()),gradient_after=float(after)),indent=2))
