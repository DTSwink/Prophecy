"""Float64 diagnostic: eliminate unsaturated motors before contact iteration.

Same capped implicit-motor/contact equations as sequential_contact_gpu. This is
an independent convergence/performance experiment, not a training controller.
"""
import json,time
from pathlib import Path
import numpy as np
OUT=Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913/causal_transfer'


def solve(s,iterations=100,hard=False):
    inv=s['inv'].astype(float);mass=np.linalg.inv(inv);free=s['free'].astype(float)
    dt=float(s['dt']);dofs=s['dofs'];gain=s['gains'];bounds=s['caps']*dt;command=s['commands']
    J=s['J'];L=s['limit_J'];nc=len(J);nl=len(L);mu=s['friction']
    physical_response=np.einsum('ij,caj->cai',inv,J)
    physical_diagonal=np.einsum('cai,cai->ca',J,physical_response)
    soft=np.zeros(nl) if hard else s['limit_compliance'];target=np.zeros(nl) if hard else s['limit_target']
    contact=np.zeros((nc,3));limits=np.zeros(nl);v=free.copy();history=[]
    previous=None
    for outer in range(30):
        requested=dt*gain*(command-v[dofs]);active=np.where(requested>bounds,1,np.where(requested<-bounds,-1,0))
        effective=mass.copy();rhs=mass@free
        for a,dof in enumerate(dofs):
            if active[a]:rhs[dof]+=active[a]*bounds[a]
            else:effective[dof,dof]+=dt*gain[a];rhs[dof]+=dt*gain[a]*command[a]
        response=np.linalg.inv(effective);base=response@rhs
        cr=np.einsum('ij,caj->cai',response,J);cd=np.einsum('cai,cai->ca',J,cr)
        lr=response@L.T;ld=np.sum(L*lr.T,axis=1)
        v=base+np.einsum('cai,ca->i',cr,contact)+lr@limits
        for it in range(iterations):
            for a in range(nl):
                value=limits[a]+(target[a]-L[a]@v-soft[a]*limits[a])/(ld[a]+soft[a])
                if not s['limit_bilateral'][a]:value=max(0,value)
                value=(limits[a]+value)*.5
                v+=lr[:,a]*(value-limits[a]);limits[a]=value
            for c in range(nc):
                if mu[c]>0:
                    # Preserve the original tangent projection metric. Changing
                    # it changes the sliding-friction fixed point, not just the
                    # convergence rate; normal rows have no such dependence.
                    tangent=contact[c,1:]-(J[c,1:]@v)/physical_diagonal[c,1:]
                    length=np.linalg.norm(tangent);bound=mu[c]*contact[c,0]
                    if length>bound:tangent*=bound/max(length,1e-30)
                    tangent=(contact[c,1:]+tangent)*.5
                    v+=cr[c,1:].T@(tangent-contact[c,1:]);contact[c,1:]=tangent
                value=max(0,contact[c,0]-(J[c,0]@v)/cd[c,0]);value=(value+contact[c,0])*.5
                v+=cr[c,0]*(value-contact[c,0]);contact[c,0]=value
        impulse=mass@(v-free)-np.einsum('cai,ca->i',J,contact)-L.T@limits
        defect=float(abs(impulse[dofs]/dt-np.clip(gain*(command-v[dofs]),-s['caps'],s['caps'])).max())
        history.append(dict(outer=outer,active=int(np.count_nonzero(active)),defect=defect))
        newreq=dt*gain*(command-v[dofs]);nextactive=np.where(newreq>bounds,1,np.where(newreq<-bounds,-1,0))
        if np.array_equal(nextactive,active):break
        if previous is not None and np.array_equal(nextactive,previous):break
        previous=active.copy()
    # Residual of the original fixed-point equations, not merely motor error.
    diag=physical_diagonal
    residual=0.
    for c in range(nc):
        normal=max(0,contact[c,0]-(J[c,0]@v)/diag[c,0]);residual=max(residual,abs(normal-contact[c,0]))
        if mu[c]>0:
            tang=contact[c,1:]-(J[c,1:]@v)/diag[c,1:];norm=np.linalg.norm(tang);bound=mu[c]*contact[c,0]
            if norm>bound:tang*=bound/max(norm,1e-30)
            residual=max(residual,float(abs(tang-contact[c,1:]).max()))
    return v,dict(history=history,motor_defect_nm=defect,contact_residual_ns=residual)


def main():
    with np.load(OUT/'contact_worst_equations.npz') as z:p={k:z[k] for k in z.files}
    w=int(p['world']);nc=int(p['ncontact'][w]);nl=int(p['nlimit'][w])
    s={k:p[k] for k in ('dt','dofs','gains','caps')};s['dt']=float(s['dt'][0])
    s.update({k:p[k][w] for k in ('inv','free','commands')})
    s.update({k:p[k][w,:nc] for k in ('J','friction')})
    s.update({k:p[k][w,:nl] for k in ('limit_J','limit_compliance','limit_target','limit_bilateral')})
    report=[]
    for n in (10,30,100,300):
        started=time.perf_counter();v,row=solve(s,n)
        row.update(iterations=n,seconds=time.perf_counter()-started)
        report.append(row);print(json.dumps(row),flush=True)
    (OUT/'block_contact_reference.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
