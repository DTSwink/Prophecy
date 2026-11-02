"""Experimental launch fusion for the unchanged sparse LDL update schedule."""
from contextlib import contextmanager
import numpy as np
import warp as wp
from mujoco_warp._src import smooth

@wp.func_native('__syncthreads();')
def block_barrier():
    pass

@wp.kernel(enable_backward=False)
def fused_factor(nv:int,nc:int,levels:int,
                 mapping:wp.array(dtype=int),rownnz:wp.array(dtype=int),rowadr:wp.array(dtype=int),
                 offsets:wp.array(dtype=int),updates:wp.array(dtype=wp.vec3i),
                 matrix:wp.array3d(dtype=float),factor:wp.array3d(dtype=float),diag:wp.array2d(dtype=float)):
    world,lane=wp.tid()
    # Exactly one complete 32-thread block per world, with no divergent barrier.
    for index in range(lane,nc,32):
        factor[world,0,index]=matrix[world,0,mapping[index]]
    block_barrier()
    for level in range(levels):
        for node in range(offsets[level]+lane,offsets[level+1],32):
            update=updates[node];i=update[0];k=update[1];ki=update[2]
            row_i=rowadr[i];row_k=rowadr[k];diag_k=row_k+rownnz[k]-1
            tmp=factor[world,0,ki]/factor[world,0,diag_k]
            for j in range(rownnz[i]):
                wp.atomic_sub(factor[world,0],row_i+j,factor[world,0,row_k+j]*tmp)
            factor[world,0,ki]=tmp
        block_barrier()
    for dof in range(lane,nv,32):
        diag[world,dof]=1.0/factor[world,0,rowadr[dof]+rownnz[dof]-1]

class FusedFactor:
    def __init__(self,m,d):
        assert m.is_sparse
        groups=[x.numpy() for x in reversed(m.qLD_updates)]
        self.offsets=wp.array(np.cumsum([0]+[len(x) for x in groups]).astype(np.int32),device=d.qpos.device)
        self.updates=wp.array(np.concatenate(groups).astype(np.int32),dtype=wp.vec3i,device=d.qpos.device)
        self.m=m;self.d=d;self.levels=len(groups);self.hits=0
        self.original=smooth._factor_i_sparse
    def apply(self,m,d,M,L,D):
        wp.launch(fused_factor,dim=(d.nworld,32),block_dim=32,
                  inputs=[m.nv,m.nC,self.levels,m.mapM2M,m.M_rownnz,m.M_rowadr,self.offsets,self.updates,M],outputs=[L,D])
    @contextmanager
    def capture(self):
        def wrapped(m,d,M,L,D):
            if m is self.m and d is self.d:
                self.hits+=1;return self.apply(m,d,M,L,D)
            return self.original(m,d,M,L,D)
        try:
            smooth._factor_i_sparse=wrapped
            yield self
        finally:smooth._factor_i_sparse=self.original
