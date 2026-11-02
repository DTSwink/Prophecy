"""Check larger/curved contact patches and replay the actual rejected equations."""
import ast,json,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Saved/MimicKitUEFN/dependencies'))
import numpy as np
import warp as wp
from contact_manifolds_gpu import allocate,group_contacts,prepare_response as manifold_response
from sequential_contact_gpu import prepare_response,prepare_limit_response
from bounded_contact_gpu import make_iteration
from test_coupled_contact_gpu import load_problem

def main():
    wp.init();wp.set_device('cuda:0');dev='cuda:0'
    sizes=[1,4,5,8,12];capacity=12;n=len(sizes)
    p=allocate(n,capacity,40,dev)
    positions=np.zeros((n*capacity,3),np.float32)
    pairs=np.tile([0,1],(n*capacity,1)).astype(np.int32)
    frames=np.tile(np.array([[0,0,1],[1,0,0],[0,1,0]],np.float32),(n*capacity,1,1))
    for w,size in enumerate(sizes):
        positions[w*capacity:(w+1)*capacity,0]=np.arange(capacity)
    p.contact_ids.assign(np.arange(n*capacity).reshape(n,capacity))
    error=wp.zeros(n,dtype=int,device=dev)
    counts=wp.array(sizes,dtype=int,device=dev)
    mu=wp.ones((n,capacity),device=dev)
    geometry=wp.array(pairs,dtype=wp.vec2i,device=dev)
    points=wp.array(positions,dtype=wp.vec3,device=dev)
    normals=wp.array(frames,dtype=wp.mat33,device=dev)
    def group():wp.launch(group_contacts,dim=n,inputs=[p,counts,mu,geometry,points,normals,error],device=dev)
    group();wp.synchronize()
    np.testing.assert_array_equal(error.numpy(),0)
    np.testing.assert_array_equal(p.count.numpy(),1)
    np.testing.assert_array_equal(p.size.numpy()[:,0],sizes)
    np.testing.assert_array_equal(p.diagnostics.numpy()[:,0],sizes)
    np.testing.assert_allclose(p.center.numpy()[:,0,0],(np.array(sizes)-1)/2)
    # Different normals must have separate centers/tangent planes, not stop.
    frames[1]=np.array([[1,0,0],[0,1,0],[0,0,1]],np.float32)
    counts.assign(np.full(n,2,np.int32));normals.assign(frames);group();wp.synchronize()
    assert p.count.numpy()[0]==2 and p.diagnostics.numpy()[0,1]==1
    np.testing.assert_array_equal(error.numpy(),0)
    # A pre-existing actual failure is never cleared by geometry processing.
    error.fill_(3);group();wp.synchronize();np.testing.assert_array_equal(error.numpy(),3)
    capture=ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023/unexpected-stop-20261023/solver_failure.npz'
    data=dict(np.load(capture));q,_=load_problem(capture,True);q.relaxation=1.
    q.response=wp.zeros(q.J.shape,device=dev)
    q.limit_response=wp.zeros(q.limit_J.shape,device=dev)
    wp.launch(prepare_response,dim=q.J.shape[:2]+(3,q.nv),inputs=[q],device=dev)
    wp.launch(prepare_limit_response,dim=q.limit_J.shape,inputs=[q],device=dev)
    wp.launch(manifold_response,dim=q.manifold.J.shape[:2]+(3,q.nv),inputs=[q.manifold,q.inv],device=dev)
    kernel=make_iteration(q.nv);q.solver_error.zero_()
    def solve():wp.launch_tiled(kernel,dim=1,inputs=[q,40],block_dim=32,device=dev)
    solve();wp.synchronize()
    velocity=q.velocity.numpy();difference=float(abs(velocity-data['velocity']).max())
    np.testing.assert_allclose(velocity,data['velocity'],atol=2e-4,rtol=2e-5)
    np.testing.assert_array_equal(q.solver_error.numpy(),0)
    assert np.isfinite(velocity).all()
    assert np.all(abs(q.motor_impulse.numpy())<=data['dt'][0]*data['caps']+1e-5)
    with wp.ScopedCapture() as graph:solve()
    wp.capture_launch(graph.graph);wp.synchronize()
    np.testing.assert_array_equal(q.velocity.numpy(),velocity)
    q.free.fill_(float('nan'));solve();wp.synchronize()
    np.testing.assert_array_equal(q.solver_error.numpy(),4)
    # Exercise the real rollout-boundary validator without constructing a world.
    tree=ast.parse((ROOT/'Labs/MimicKitTransfer/contact_engine.py').read_text())
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef))
    method=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='validate_transfer_solver')
    scope={'np':np};exec(compile(ast.Module(body=[method],type_ignores=[]),'actual_validator','exec'),scope)
    array=lambda values:types.SimpleNamespace(numpy=lambda:np.array(values))
    geometry=np.array([[5,0]])
    problem=types.SimpleNamespace(manifold=types.SimpleNamespace(diagnostics=types.SimpleNamespace(numpy=lambda:geometry)),
        stats=array([[32.82]]),roundoff_warnings=array([0]),convergence_warnings=array([0]))
    engine=types.SimpleNamespace(transfer_contact=types.SimpleNamespace(error=array([0]),p=problem),
        _bounded_sequential=True,transfer_profile_report={'profile':'bounded_jolt_40_20'})
    validate=scope['validate_transfer_solver'];warning=validate(engine)
    assert warning['maximum_contact_patch_points']==5 and validate(engine) is None
    geometry[0,1]=1;assert validate(engine)['separate_normal_patches'] and validate(engine) is None
    engine.transfer_contact.error=array([4])
    try:validate(engine)
    except FloatingPointError:pass
    else:raise AssertionError('Validator accepted an actual numerical failure')
    report=dict(patch_sizes=sizes,all_points_retained=True,distinct_normals_separated=True,
        captured_world=int(data['original_world']),captured_patch_size=5,
        captured_velocity_difference=difference,cuda_graph=True,torque_caps=True,nonfinite_rejected=True,
        real_validator_warns_and_continues=True,duplicate_warnings_suppressed=True)
    (capture.parent/'warning-fix-tests.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

if __name__=='__main__':main()
