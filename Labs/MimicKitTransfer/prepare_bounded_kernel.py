"""Generate the isolated register version of the bounded sequential solve."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'

def generate():
    block=(ROOT/'Labs/MimicKitTransfer/block_contact_gpu.py').read_text()
    start=block.index('                for c in range(p.nlimit[w]):',block.index('for it in range(iterations):'))
    end=block.index('                if unchanged:break',start)
    rows=block[start:end]
    rows='\n'.join(line[4:] for line in rows.splitlines())+'\n'
    rows=rows.replace('p.effective_limit_diagonal','p.limit_diagonal').replace('p.effective_normal_diagonal[w,c]','p.diagonal[w,c,0]')
    rows=rows.replace('p.block_metric[w,c,0]','p.diagonal[w,c,1]').replace('p.block_metric[w,c,1]','p.diagonal[w,c,2]').replace('p.block_metric[w,g,2]','p.manifold.diagonal[w,g,2]')
    rows=rows.replace('+1.0*','+p.relaxation*')
    rows='\n'.join(line for line in rows.splitlines() if 'unchanged=False' not in line)+'\n'
    head='''"""Register-resident finite-budget sequential impulses. Diagnostic candidate.

Same row order and relaxation as the original scalar solver; float32 reduction
order differs. A bounded solve is approximate, unlike the converged block profile.
"""
import warp as wp
from sequential_contact_gpu import ContactProblem,friction_bound
from block_contact_gpu import warp_sum,warp_barrier,warp_max

def make_iteration(nv):
    assert nv<=64
    @wp.kernel(module='unique',enable_backward=False)
    def solve(p:ContactProblem,iterations:int):
        w,lane=wp.tid();dt=p.dt[0];k0=lane;k1=lane+32
        v0=float(0.);v1=float(0.)
        if k0<nv:v0=p.free[w,k0]
        if k1<nv:v1=p.free[w,k1]
        for a in range(lane,p.nmotor,32):p.motor_impulse[w,a]=0.
        for c in range(lane,p.ncontact[w],32):
            for a in range(3):p.contact_impulse[w,c,a]=0.
        for c in range(lane,p.nlimit[w],32):p.limit_impulse[w,c]=0.
        if p.manifold.enabled:
            for g in range(lane,p.manifold.count[w],32):p.manifold.impulse[w,g,2]=0.
        v0=warp_barrier(v0)
        for it in range(iterations):
            for a in range(p.nmotor):
                dof=p.dofs[a];old=p.motor_impulse[w,a]
                speed=float(0.)
                if dof==k0:speed=v0
                if dof==k1:speed=v1
                speed=warp_sum(speed)
                compliance=1./(dt*p.gains[a]);cap=dt*p.caps[a]
                impulse=wp.clamp(old+(p.commands[w,a]-speed-compliance*old)/(p.inv[w,dof,dof]+compliance),-cap,cap)
                impulse=old+p.relaxation*(impulse-old)
                if k0<nv:v0+=p.inv[w,dof,k0]*(impulse-old)
                if k1<nv:v1+=p.inv[w,dof,k1]*(impulse-old)
                if lane==0:p.motor_impulse[w,a]=impulse
                v0=warp_barrier(v0)
'''
    tail='''        if k0<nv:p.velocity[w,k0]=v0
        if k1<nv:p.velocity[w,k1]=v1
        defect=float(0.)
        for a in range(p.nmotor):
            dof=p.dofs[a];speed=float(0.)
            if dof==k0:speed=v0
            if dof==k1:speed=v1
            speed=warp_sum(speed)
            expected=wp.clamp(p.gains[a]*(p.commands[w,a]-speed),-p.caps[a],p.caps[a])
            defect=wp.max(defect,wp.abs(p.motor_impulse[w,a]/dt-expected))
        if lane==0:p.stats[w,0]=defect
        if not wp.isfinite(v0) or not wp.isfinite(v1) or not wp.isfinite(defect):
            p.solver_error[w]=4
    return solve
'''
    path=OUT/'bounded_contact_gpu.py';path.write_text(head+rows+tail)
    return path

if __name__=='__main__':print(generate())
