"""Independent float64 diagnosis of the saved active-set cycle; no physics edits."""
import json,time,sys
from pathlib import Path
import numpy as np
OUT=Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913/causal_transfer'


class Equations:
    def __init__(self,path):
        p=dict(np.load(path));w=int(np.flatnonzero(p['errors'])[0]);self.world=w
        self.inv=p['inv'][w].astype(float);nv=self.inv.shape[0];self.M=p['mass'][w,:nv,:nv].astype(float)
        self.free=p['free'][w].astype(float);self.dt=float(p['dt'][0]);self.dofs=p['dofs']
        self.gain=p['gains'];self.cap=p['caps'];self.cmd=p['commands'][w]
        nc=int(p['ncontact'][w]);nl=int(p['nlimit'][w]);ng=int(p['manifold_count'][w])
        self.J=p['J'][w,:nc].astype(float);self.L=p['limit_J'][w,:nl].astype(float)
        self.diag=p['diagonal'][w,:nc].astype(float);self.mu=p['friction'][w,:nc]
        self.group=p['manifold_group'][w,:nc];self.radius=p['manifold_radius'][w,:nc]
        self.size=p['manifold_size'][w,:ng];self.S=p['manifold_J'][w,:ng,2].astype(float)
        self.sd=p['manifold_diagonal'][w,:ng,2].astype(float)
        assert np.all(p['limit_compliance'][w,:nl]==0) and np.all(p['limit_target'][w,:nl]==0)
        assert np.all(p['limit_bilateral'][w,:nl]==0)

    def empty(self):return np.zeros((len(self.J),3)),np.zeros(len(self.L)),np.zeros(len(self.S))

    def contacts(self,v,contact,limit,spin,inverse,iterations,motor=None):
        cr=self.J@inverse;lr=self.L@inverse;sr=self.S@inverse
        cd=np.sum(self.J*cr,axis=2);ld=np.sum(self.L*lr,axis=1)
        for _ in range(iterations):
            if motor is not None:
                for a,j in enumerate(self.dofs):
                    comp=1/(self.dt*self.gain[a]);bound=self.dt*self.cap[a]
                    value=np.clip(motor[a]+(self.cmd[a]-v[j]-comp*motor[a])/(inverse[j,j]+comp),-bound,bound)
                    value=(value+motor[a])*.5;v+=inverse[:,j]*(value-motor[a]);motor[a]=value
            for a in range(len(limit)):
                value=max(0,limit[a]-self.L[a]@v/ld[a]);value=(value+limit[a])*.5
                v+=lr[a]*(value-limit[a]);limit[a]=value
            for c in range(len(contact)):
                if self.mu[c]>0:
                    g=self.group[c];mask=self.group==g;bound=self.mu[c]*contact[mask,0].sum()
                    t=contact[c,1:]-self.J[c,1:]@v/self.diag[c,1:]
                    t*=min(1,bound/max(np.linalg.norm(t),1e-30));t=(t+contact[c,1:])*.5
                    v+=cr[c,1:].T@(t-contact[c,1:]);contact[c,1:]=t
                    if self.size[g]>1:
                        bound=self.mu[c]*(self.radius[mask]*contact[mask,0]).sum()
                        value=np.clip(spin[g]-self.S[g]@v/self.sd[g],-bound,bound);value=(value+spin[g])*.5
                        v+=sr[g]*(value-spin[g]);spin[g]=value
                value=max(0,contact[c,0]-self.J[c,0]@v/cd[c,0]);value=(value+contact[c,0])*.5
                v+=cr[c,0]*(value-contact[c,0]);contact[c,0]=value
        return v

    def defect(self,v,c,l,s):
        impulse=self.M@(v-self.free)-np.einsum('caj,ca->j',self.J,c)-self.L.T@l-self.S.T@s
        expected=np.clip(self.gain*(self.cmd-v[self.dofs]),-self.cap,self.cap)
        motor=float(abs(impulse[self.dofs]/self.dt-expected).max())
        before=v.copy();after=self.contacts(v.copy(),c.copy(),l.copy(),s.copy(),self.inv,1)
        return dict(motor_defect_nm=motor,contact_iteration_delta=float(abs(after-before).max()))

    def scalar(self,n):
        c,l,s=self.empty();v=self.contacts(self.free.copy(),c,l,s,self.inv,n,np.zeros(len(self.dofs)))
        return v,c,l,s

    def block(self,damping,seed_iterations=50):
        guess,*_=self.scalar(seed_iterations);c,l,s=self.empty();history=[]
        for outer in range(60):
            req=self.dt*self.gain*(self.cmd-guess[self.dofs]);bound=self.dt*self.cap
            active=np.where(req>bound,1,np.where(req<-bound,-1,0))
            eff=self.M.copy();rhs=self.M@self.free
            for a,j in enumerate(self.dofs):
                if active[a]:rhs[j]+=active[a]*bound[a]
                else:eff[j,j]+=self.dt*self.gain[a];rhs[j]+=self.dt*self.gain[a]*self.cmd[a]
            inv=np.linalg.inv(eff)
            v=inv@(rhs+np.einsum('caj,ca->j',self.J,c)+self.L.T@l+self.S.T@s)
            self.contacts(v,c,l,s,inv,100)
            newreq=self.dt*self.gain*(self.cmd-v[self.dofs]);nextactive=np.where(newreq>bound,1,np.where(newreq<-bound,-1,0))
            row=dict(outer=outer,changed=np.flatnonzero(active!=nextactive).tolist(),**self.defect(v,c,l,s));history.append(row)
            if np.array_equal(active,nextactive):break
            guess=guess+damping*(v-guess)
        return v,dict(damping=damping,seed_iterations=seed_iterations,converged=not history[-1]['changed'],history=history)


def main(graph=False):
    e=Equations(OUT/('contact_first_solver_failure_graph.npz' if graph else 'contact_first_solver_failure.npz'));start=time.perf_counter();reference,c,l,s=e.scalar(3000)
    baseline=e.defect(reference,c,l,s);rows=[];print('SCALAR',json.dumps(baseline),flush=True)
    for damping,seed in ((1.,50),(.5,50),(.25,50),(.5,0)):
        value,row=e.block(damping,seed);row['difference_from_scalar']=float(abs(value-reference).max());rows.append(row)
        print(json.dumps(row),flush=True)
    (OUT/('block_failure_graph.json' if graph else 'block_failure.json')).write_text(json.dumps(dict(world=e.world,scalar=baseline,rows=rows,seconds=time.perf_counter()-start),indent=2))


if __name__=='__main__':main('--graph' in sys.argv)
