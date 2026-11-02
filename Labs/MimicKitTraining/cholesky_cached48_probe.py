# Copyright 2025 The Newton Developers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Unvalidated candidate retaining all native 16-column blocks and 48 padded rows.

Derived from mujoco_warp._src.block_cholesky. All three block shapes and the
ordering of every block update remain unchanged; tiles stay resident between uses. No deployment until
real-state exact-output parity and full-update timing both pass.
"""
import inspect
from contextlib import contextmanager
import warp as wp
from mujoco_warp._src import solver, types


@wp.kernel(enable_backward=False)
def cached48(done:wp.array(dtype=bool), grad:wp.array3d(dtype=float),
           h:wp.array3d(dtype=float), factor:wp.array3d(dtype=float),
           result:wp.array3d(dtype=float)):
    w=wp.tid()
    if done[w]:return
    a=h[w]
    l=factor[w]
    b=grad[w]
    x=result[w]
    # Native k=0 block and both panels below it.
    a00=wp.tile_load(a,shape=(16,16),offset=(0,0),storage='shared')
    l00=wp.tile_cholesky(a00)
    a10=wp.tile_load(a,shape=(16,16),offset=(16,0),storage='shared')
    wp.tile_lower_solve_inplace(l00,wp.tile_transpose(a10))
    a20=wp.tile_load(a,shape=(16,16),offset=(32,0),storage='shared')
    wp.tile_lower_solve_inplace(l00,wp.tile_transpose(a20))
    # Native k=16 block and its trailing panel.
    a11=wp.tile_load(a,shape=(16,16),offset=(16,16),storage='shared')
    wp.tile_matmul(a10,wp.tile_transpose(a10),a11,alpha=-1.0)
    l11=wp.tile_cholesky(a11)
    a21=wp.tile_load(a,shape=(16,16),offset=(32,16),storage='shared')
    wp.tile_matmul(a20,wp.tile_transpose(a10),a21,alpha=-1.0)
    wp.tile_lower_solve_inplace(l11,wp.tile_transpose(a21))
    # Native k=32 updates in their original order, including identity padding.
    a22=wp.tile_load(a,shape=(16,16),offset=(32,32),storage='shared')
    wp.tile_matmul(a20,wp.tile_transpose(a20),a22,alpha=-1.0)
    wp.tile_matmul(a21,wp.tile_transpose(a21),a22,alpha=-1.0)
    l22=wp.tile_cholesky(a22)
    wp.tile_store(l,l00,offset=(0,0));wp.tile_store(l,a10,offset=(16,0))
    wp.tile_store(l,a20,offset=(32,0));wp.tile_store(l,l11,offset=(16,16))
    wp.tile_store(l,a21,offset=(32,16));wp.tile_store(l,l22,offset=(32,32))
    r0=wp.tile_load(b,shape=(16,1),offset=(0,0),storage='shared')
    r1=wp.tile_load(b,shape=(16,1),offset=(16,0),storage='shared')
    r2=wp.tile_load(b,shape=(16,1),offset=(32,0),storage='shared')
    wp.tile_lower_solve_inplace(l00,r0)
    wp.tile_matmul(a10,r0,r1,alpha=-1.0)
    wp.tile_lower_solve_inplace(l11,r1)
    wp.tile_matmul(a20,r0,r2,alpha=-1.0)
    wp.tile_matmul(a21,r1,r2,alpha=-1.0)
    wp.tile_lower_solve_inplace(l22,r2)
    wp.tile_upper_solve_inplace(wp.tile_transpose(l22),r2)
    wp.tile_matmul(wp.tile_transpose(a21),r2,r1,alpha=-1.0)
    wp.tile_upper_solve_inplace(wp.tile_transpose(l11),r1)
    wp.tile_matmul(wp.tile_transpose(a10),r1,r0,alpha=-1.0)
    wp.tile_matmul(wp.tile_transpose(a20),r2,r0,alpha=-1.0)
    wp.tile_upper_solve_inplace(wp.tile_transpose(l00),r0)
    wp.tile_store(x,r0,offset=(0,0));wp.tile_store(x,r1,offset=(16,0));wp.tile_store(x,r2,offset=(32,0))


@wp.kernel(enable_backward=False)
def audit_edge(done:wp.array(dtype=bool), reference:wp.array3d(dtype=float),
               actual:wp.array3d(dtype=float),counts:wp.array2d(dtype=int),maximum:wp.array(dtype=float)):
    w,k=wp.tid()
    if done[w]:return
    expected=reference[w,k,0];value=actual[w,k,0]
    wp.atomic_add(counts,w,0,1)
    if expected!=value:
        wp.atomic_add(counts,w,1,1)
        wp.atomic_max(maximum,w,wp.abs(expected-value))
    if not wp.isfinite(expected) or not wp.isfinite(value):wp.atomic_add(counts,w,2,1)


class CachedBlocks48:
    def __init__(self,m,d):
        assert m.nv==40 and m.nv_pad==48 and types.TILE_SIZE_JTDAJ_DENSE==16
        self.kernel=solver.update_gradient_cholesky_blocked(16,48)
        self.original=wp.launch_tiled
        self.hits=0
        self.audit=False
        self.reference=wp.zeros((d.nworld,48,1),dtype=float)
        self.reference_factor=wp.zeros((d.nworld,48,48),dtype=float)
        self.counts=wp.zeros((d.nworld,3),dtype=int)
        self.maximum=wp.zeros(d.nworld,dtype=float)

    def launch(self,kernel,*args,**kwargs):
        if kernel is self.kernel:
            assert not args, 'Pinned blocked solve uses named launch arguments'
            inputs=list(kwargs['inputs'])
            output=kwargs['outputs'][0]
            if self.audit:
                reference_kwargs=dict(kwargs,inputs=[*inputs[:3],self.reference_factor],outputs=[self.reference])
                self.original(kernel,**reference_kwargs)
            self.hits+=1
            result=self.original(cached48,**kwargs)
            if self.audit:
                wp.launch(audit_edge,dim=(self.reference.shape[0],48),
                          inputs=[inputs[0],self.reference,output,self.counts,self.maximum])
            return result
        return self.original(kernel,*args,**kwargs)

    @contextmanager
    def capture(self):
        self.hits=0
        previous=wp.launch_tiled
        self.original=previous
        try:
            wp.launch_tiled=self.launch
            yield self
        finally:wp.launch_tiled=previous
