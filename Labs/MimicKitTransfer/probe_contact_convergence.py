"""Float64 convergence audit of the exact worst saved coupled contact problem."""
import json,time
from pathlib import Path
import numpy as np
OUT=Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913/causal_transfer'


def main(block_tangent=False,relaxation=1.):
    p=np.load(OUT/'contact_worst_equations.npz');w=int(p['world']);dt=float(p['dt'][0])
    inv=p['inv'][w].astype('float64');v=p['free'][w].astype('float64');dofs=p['dofs']
    gain=p['gains'];cap=p['caps']*dt;commands=p['commands'][w];motor=np.zeros(len(dofs))
    compliance=1/(dt*gain)
    nc=int(p['ncontact'][w]);nl=int(p['nlimit'][w]);J=p['J'][w,:nc].astype('float64')
    response=np.einsum('ij,caj->cai',inv,J);diag=np.einsum('cai,cai->ca',J,response)
    mu=p['friction'][w,:nc];contact=np.zeros((nc,3))
    L=p['limit_J'][w,:nl].astype('float64');lr=inv@L.T;ld=np.diag(L@lr)
    soft=p['limit_compliance'][w,:nl];target=p['limit_target'][w,:nl];bilateral=p['limit_bilateral'][w,:nl]
    limits=np.zeros(nl);records=[];start=time.perf_counter()
    tangent_inverse=[np.linalg.inv(J[c,1:]@inv@J[c,1:].T) if mu[c]>0 else None for c in range(nc)]
    for it in range(1,3001):
        for a,dof in enumerate(dofs):
            value=np.clip(motor[a]+(commands[a]-v[dof]-compliance[a]*motor[a])/(inv[dof,dof]+compliance[a]),-cap[a],cap[a])
            value=motor[a]+relaxation*(value-motor[a])
            v+=inv[:,dof]*(value-motor[a]);motor[a]=value
        for a in range(nl):
            value=limits[a]+(target[a]-L[a]@v-soft[a]*limits[a])/(ld[a]+soft[a])
            if not bilateral[a]:value=max(0,value)
            value=limits[a]+relaxation*(value-limits[a])
            v+=lr[:,a]*(value-limits[a]);limits[a]=value
        for c in range(nc):
            if mu[c]>0:
                speed=J[c,1:]@v
                delta=tangent_inverse[c]@speed if block_tangent else speed/diag[c,1:]
                tangent=contact[c,1:]-delta
                norm=np.linalg.norm(tangent);bound=mu[c]*contact[c,0]
                if norm>bound:tangent*=bound/max(norm,1e-30)
                tangent=contact[c,1:]+relaxation*(tangent-contact[c,1:])
                v+=response[c,1:].T@(tangent-contact[c,1:]);contact[c,1:]=tangent
            normal=max(0,contact[c,0]-(J[c,0]@v)/diag[c,0])
            normal=contact[c,0]+relaxation*(normal-contact[c,0])
            v+=response[c,0]*(normal-contact[c,0]);contact[c,0]=normal
        assert np.isfinite(v).all()
        if it in (10,30,100,299,300,301,999,1000,1001,3000):
            residual=float(abs(motor/dt-np.clip(gain*(commands-v[dofs]),-p['caps'],p['caps'])).max())
            row=dict(iterations=it,motor_residual_nm=residual,
                     difference_from_gpu100_rad_s=float(abs(v-p['velocity'][w]).max()),
                     normal_impulse_sum_ns=float(contact[:,0].sum()),
                     seconds=time.perf_counter()-start)
            records.append(row);print(json.dumps(row),flush=True)
    result=dict(tick=int(p['tick']),world=w,contacts=nc,soft_limits=nl,block_tangent=block_tangent,
                relaxation=relaxation,records=records)
    name='contact_convergence'+('_block' if block_tangent else '')+('_relaxed' if relaxation!=1 else '')+'.json'
    (OUT/name).write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':
    main();main(True);main(False,.5)
