"""Capture first rejected GPU equation without per-substep host synchronization."""
import numpy as np
import warp as wp


@wp.kernel(enable_backward=False)
def mark(error:wp.array(dtype=int),seen:wp.array(dtype=int),condition:wp.array(dtype=int)):
    condition[0]=0
    if seen[0]==0:
        for w in range(error.shape[0]):
            if error[w]!=0:condition[0]=1;seen[0]=1


class SolverFailureCapture:
    def __init__(self,custom,data):
        fields=('inv','free','commands','J','diagonal','ncontact','nlimit','limit_J',
            'limit_diagonal','limit_target','limit_compliance','limit_bilateral','friction',
            'velocity','motor_impulse','contact_impulse','limit_impulse','stats','dofs','gains','caps','dt')
        source={name:getattr(custom.p,name) for name in fields}
        if custom.p.manifold.enabled:
            for name in ('count','group','size','radius','J','diagonal','impulse'):
                source['manifold_'+name]=getattr(custom.p.manifold,name)
        source.update(qpos=data.qpos,qvel=data.qvel,mass=data.qM,errors=custom.error)
        self.snapshot={name:wp.empty_like(value) for name,value in source.items()}
        self.seen=wp.zeros(1,dtype=int,device=data.qvel.device)
        condition=wp.zeros_like(self.seen)
        def save():
            for name,value in source.items():wp.copy(self.snapshot[name],value)
        original=custom.solve
        def solve(m,d):
            original(m,d)
            wp.launch(mark,dim=1,inputs=[custom.error,self.seen,condition],device=d.qvel.device)
            wp.capture_if(condition,on_true=save)
        custom.solve=solve

    def save(self,path):
        assert int(self.seen.numpy()[0])==1
        data={name:value.numpy() for name,value in self.snapshot.items()}
        world=int(np.flatnonzero(data['errors'])[0])
        for name,value in data.items():
            if name not in ('dofs','gains','caps','dt'):data[name]=value[world:world+1]
        data['original_world']=np.array(world)
        assert not path.exists(),'Preserve previous failed equations'
        np.savez_compressed(path,**data)
