import math,torch
from idle_wobble import IdleWobble

def run(device='cpu'):
    torch.manual_seed(4)
    n=8;b=15;obj=IdleWobble(n,b,device)
    kick=torch.full((n,),-1,device=device,dtype=torch.long)
    active=torch.ones(n,device=device,dtype=torch.bool);active[-1]=False
    result=[]
    for t in range(150):
        v=torch.zeros(n,b,3,device=device);w=torch.zeros_like(v)
        v[0,:,0]=max(0,3-t/30) # fast straight stop
        v[1,:,0]=.2*math.sin(t/30*2*math.pi*.6)
        v[2,:,0]=.2*math.cos(t/30*2*math.pi*.6);v[2,:,1]=.2*math.sin(t/30*2*math.pi*.6)
        w[3,:,0]=.7*math.sin(t/30*2*math.pi*.6)
        v[4,:,0]=.2*math.sin(t/30*2*math.pi*5)
        v[5]=v[1] if t<100 else 0
        v[6]=v[1];v[7]=v[1]
        if t==90:kick[6]=90
        result.append(obj.append(v,w,kick,active).clone())
    r=torch.stack(result)
    assert float(r[:,0].max())<1e-6
    assert (r[40:90,1:5].mean(0)>1e-4).all()
    assert (r[100:,5]==0).all() and (r[:,7]==0).all()
    assert float(r[90,6])==0
    old=obj.vector[1].clone();obj.reset(torch.tensor([0],device=device));torch.testing.assert_close(old,obj.vector[1])
    # Constant angular spin stays outside this oscillation detector's purpose.
    obj=IdleWobble(1,b,device)
    for _ in range(60):
        cost=obj.append(torch.ones(1,b,3,device=device),torch.ones(1,b,3,device=device),kick[:1],active[:1])
        assert float(cost)<1e-5
    if device=='cuda':
        obj=IdleWobble(8,b,device);v=torch.randn(8,b,3,device=device);w=torch.randn_like(v)
        saved={k:getattr(obj,k).clone() for k in obj.buffer_names}
        stream=torch.cuda.Stream();stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(stream):
            for _ in range(3):obj.append(v,w,kick,active)
        torch.cuda.current_stream().wait_stream(stream)
        graph=torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph):out=obj.append(v,w,kick,active)
        for k,value in saved.items():getattr(obj,k).copy_(value)
        graph.replay();actual=out.clone()
        for k,value in saved.items():getattr(obj,k).copy_(value)
        expected=obj.append(v,w,kick,active);torch.testing.assert_close(actual,expected)
    print('IdleWobble tests passed',device)

if __name__=='__main__':
    import sys
    run(sys.argv[1] if len(sys.argv)>1 else 'cpu')
