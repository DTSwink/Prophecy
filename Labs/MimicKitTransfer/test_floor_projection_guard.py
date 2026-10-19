"""Exact shape/FK checks, floor-blocked corrections, capture and GPU timing."""
import json,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKitUEFN/dependencies'))
import numpy as np,mujoco,warp as wp
from floor_projection_guard import FloorProjectionGuard,floor_fk,floor_height
from floor_projection_parallel import chain_height

@wp.kernel
def heights(s:__import__('floor_projection_guard').FloorGeometry,q:wp.array2d(dtype=float),h:wp.array2d(dtype=float)):
    w=wp.tid();floor_fk(s,q,q,w,0.)
    for g in range(h.shape[1]):h[w,g]=floor_height(s,w,g)

@wp.kernel
def chain_heights(s:__import__('floor_projection_guard').FloorGeometry,q:wp.array2d(dtype=float),h:wp.array2d(dtype=float)):
    w,g=wp.tid();h[w,g]=chain_height(s,q,q,w,0.,g)

def cpu_heights(m,d,ids):
    mujoco.mj_kinematics(m,d);out=[]
    for g in ids:
        size=m.geom_size[g];mat=d.geom_xmat[g].reshape(3,3);extent=size[0]
        if m.geom_type[g]==3:extent+=size[1]*abs(mat[2,2])
        elif m.geom_type[g]==6:extent=abs(mat[2])@size
        out.append(d.geom_xpos[g,2]-extent)
    return np.array(out)

def main():
    parallel='--parallel' in sys.argv
    # Real compound model, with both hinge and free joints. A ball-joint model
    # is also covered below; production Newton converts the same rig to balls.
    import xml.etree.ElementTree as ET
    xml=ET.parse(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml')
    ET.SubElement(xml.getroot().find('worldbody'),'geom',name='floor',type='plane',size='0 0 .1')
    models=[mujoco.MjModel.from_xml_string(ET.tostring(xml.getroot(),encoding='unicode')),
        mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom type="plane" size="0 0 .1"/><body pos="0 0 1"><freejoint/><geom type="box" size=".1 .2 .1"/><body pos="0 0 -.3"><joint type="ball" pos=".1 0 0"/><geom type="capsule" size=".08 .3" pos=".1 0 -.25"/></body></body></worldbody></mujoco>')]
    wp.init();device='cuda:0';rng=np.random.default_rng(731);reports=[]
    for m in models:
        n=512;d=mujoco.MjData(m);before=[];after=[];hb=[];ha=[]
        gpu=SimpleNamespace(qpos=wp.empty((n,m.nq),dtype=float,device=device),nworld=n)
        guard=FloorProjectionGuard(m,gpu,device,parallel=parallel)
        for i in range(n):
            d.qpos[:]=m.qpos0;v=rng.normal(0,.25,m.nv);v[:3]=0
            mujoco.mj_integratePos(m,d.qpos,v,1.)
            h=cpu_heights(m,d,guard.geom_ids);d.qpos[2]+=-h.min()+(.001 if i%4 else -.02)
            before.append(d.qpos.copy());hb.append(cpu_heights(m,d,guard.geom_ids))
            v=rng.normal(0,.1,m.nv);v[:3]=rng.normal(0,.02,3)
            if i%8:mujoco.mj_integratePos(m,d.qpos,v,1.)
            after.append(d.qpos.copy());ha.append(cpu_heights(m,d,guard.geom_ids))
        before=np.array(before,dtype=np.float32);after=np.array(after,dtype=np.float32)
        gpu.qpos.assign(before);guard.save_before()
        hgpu=wp.empty((n,len(guard.geom_ids)),dtype=float,device=device)
        wp.launch(heights,dim=n,inputs=[guard.s,gpu.qpos,hgpu],device=device)
        fkerr=float(abs(hgpu.numpy()-hb).max());assert fkerr<3e-6,fkerr
        wp.launch(chain_heights,dim=(n,len(guard.geom_ids)),inputs=[guard.s,gpu.qpos,hgpu],device=device)
        chainerr=float(abs(hgpu.numpy()-hb).max());assert chainerr<3e-6,chainerr
        gpu.qpos.assign(after);guard.apply();accepted=gpu.qpos.numpy()
        # Launch scheduling must not alter even the accepted float32 bits.
        from floor_projection_guard import guard as guard_kernel
        gpu.qpos.assign(after)
        wp.launch(guard_kernel,dim=n,inputs=[guard.s,guard.before,gpu.qpos,guard.fractions,guard.blocked],device=device,block_dim=256)
        schedule_error=float(abs(accepted-gpu.qpos.numpy()).max())
        if not parallel:np.testing.assert_array_equal(accepted,gpu.qpos.numpy())
        gpu.qpos.assign(accepted)
        wp.launch(heights,dim=n,inputs=[guard.s,gpu.qpos,hgpu],device=device)
        actual=hgpu.numpy();bound=np.minimum(np.array(hb),-2e-5)
        violation=float(np.maximum(0,bound-actual).max());assert violation<3e-6,violation
        clear=(np.array(ha)>=bound+3e-6).all(-1)
        np.testing.assert_array_equal(accepted[clear],after[clear])
        fractions=guard.fractions.numpy();assert np.any(fractions<1) and np.any(fractions==1)
        proposed=wp.array(after,device=device)
        with wp.ScopedCapture(device=device) as capture:
            wp.copy(gpu.qpos,proposed);guard.apply()
        wp.capture_launch(capture.graph);np.testing.assert_array_equal(accepted,gpu.qpos.numpy())
        for _ in range(5):wp.capture_launch(capture.graph)
        wp.synchronize();start=time.perf_counter()
        for _ in range(50):wp.capture_launch(capture.graph)
        wp.synchronize();ms=(time.perf_counter()-start)*1000/50
        reports.append(dict(nq=m.nq,worlds=n,fk_error_m=fkerr,chain_fk_error_m=chainerr,new_penetration_max_m=violation,
            blocked_worlds=int((fractions<1).sum()),unchanged_clear_worlds=int(clear.sum()),capture_exact=True,parallel=parallel,serial_difference=schedule_error,gpu_ms=ms))
    out=ROOT/'Saved/MimicKitEquipment/floor-recovery';out.mkdir(exist_ok=True)
    (out/('guard-parallel-unit.json' if parallel else 'guard-unit.json')).write_text(json.dumps(reports,indent=2));print(json.dumps(reports),flush=True)
if __name__=='__main__':main()
