"""Bounded cheap branch search followed by the original solver for hard worlds.

Diagnostic only until frozen-policy and full-size measurements pass.
The original fallback, rejection thresholds and physical parameters are retained.
"""
import importlib.util
import sys
from pathlib import Path
import warp as wp
from sequential_contact_gpu import ContactProblem


@wp.kernel(enable_backward=False)
def retry_legacy(p: ContactProblem):
    w=wp.tid()
    if p.solver_error[w]==5:
        p.solver_error[w]=0
        p.warm_state[w]=-1


def module_from_file(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def adapter_class(source,output):
    source=Path(source);output=Path(output)
    text=(source/'block_contact_gpu.py').read_text()
    assert text.count('for outer in range(60):')==2
    path=output/'staged_block.py'
    path.write_text(text.replace('for outer in range(60):','for outer in range(4):'))
    module_from_file('staged_block',path)
    text=(source/'sequential_contact_adapter.py').read_text()
    text=text.replace('self.seed_iterations=seed_iterations','self.seed_iterations=16\n        self.iterations=24')
    text=text.replace('from block_contact_gpu import make_block_iteration','from staged_block import make_block_iteration')
    anchor='self.retry_block_kernel=make_block_iteration(nv,p.nmotor,warm_start=True,retry=True)'
    assert text.count(anchor)==1
    text=text.replace(anchor,anchor+'\n            from block_contact_gpu import make_block_iteration as make_legacy\n            self.legacy_block_kernel=make_legacy(nv,p.nmotor,warm_start=True,retry=True)')
    anchor='            wp.launch_tiled(self.coupled_kernel,dim=self.coupled_slots,'
    assert text.count(anchor)==1
    text=text.replace(anchor,'''            from staged_contact_candidate import retry_legacy
            wp.launch(retry_legacy,dim=d.nworld,inputs=[p],device=dev)
            wp.launch_tiled(self.retry_seed_kernel,dim=d.nworld,inputs=[p,50],block_dim=32,device=dev)
            wp.launch_tiled(self.legacy_block_kernel,dim=d.nworld,inputs=[p,d.qM,self.identity,100,self.error],block_dim=32,device=dev)
'''+anchor)
    path=output/'staged_adapter.py';path.write_text(text)
    return module_from_file('staged_adapter',path).SequentialContactAdapter


def install(engine,source,output):
    cls=adapter_class(source,output)
    s=engine._solver;m=s.mjw_model;d=s.mjw_data
    adapter=cls(m,d,s.mj_model,engine._uefn_motors,allow_soft_limits=True,relaxation=.5,hard_limit_control=True,block_motors=True,manifolds=True,jolt_limit_axes=True)
    m.transfer_contact_test=None;adapter.install();engine.transfer_contact=adapter
    engine._build_graphs()
