"""Experimental matched-contact impulse cache, isolated from production."""
import warp as wp
from sequential_contact_gpu import ContactProblem

@wp.struct
class Cache:
    count:wp.array(dtype=int)
    group_count:wp.array(dtype=int)
    pairs:wp.array2d(dtype=wp.vec2i)
    pos:wp.array2d(dtype=wp.vec3)
    normal:wp.array2d(dtype=wp.vec3)
    impulse:wp.array2d(dtype=float)
    used:wp.array2d(dtype=int)
    group_pairs:wp.array2d(dtype=wp.vec2i)
    center:wp.array2d(dtype=wp.vec3)
    group_normal:wp.array2d(dtype=wp.vec3)
    tangent:wp.array2d(dtype=wp.vec3)
    spin:wp.array2d(dtype=float)
    hint:wp.array3d(dtype=float)
    spin_hint:wp.array2d(dtype=float)

def allocate(n,nc,dev):
    c=Cache();z=lambda shape,dtype=float:wp.zeros(shape,dtype=dtype,device=dev)
    c.count=z(n,int);c.group_count=z(n,int);c.pairs=z((n,nc),wp.vec2i)
    c.pos=z((n,nc),wp.vec3);c.normal=z((n,nc),wp.vec3);c.impulse=z((n,nc));c.used=z((n,nc),int)
    c.group_pairs=z((n,nc),wp.vec2i);c.center=z((n,nc),wp.vec3);c.group_normal=z((n,nc),wp.vec3)
    c.tangent=z((n,nc),wp.vec3);c.spin=z((n,nc));c.hint=z((n,nc,3));c.spin_hint=z((n,nc))
    return c

@wp.kernel(enable_backward=False)
def match(p:ContactProblem,c:Cache,geom:wp.array(dtype=wp.vec2i),pos:wp.array(dtype=wp.vec3),frame:wp.array(dtype=wp.mat33)):
    w=wp.tid()
    for old in range(c.count[w]):c.used[w,old]=0
    for i in range(p.ncontact[w]):
        for a in range(3):c.hint[w,i,a]=0.
        ident=p.manifold.contact_ids[w,i];pair=geom[ident];normal=frame[ident][0]
        best=int(-1);distance=float(.0004)
        for old in range(c.count[w]):
            other=c.pairs[w,old]
            if pair[0]!=other[0] or pair[1]!=other[1] or c.used[w,old]!=0:continue
            if wp.dot(normal,c.normal[w,old])<.999:continue
            gap=wp.length_sq(pos[ident]-c.pos[w,old])
            if gap<distance:best=old;distance=gap
        if best>=0:
            c.used[w,best]=1;c.hint[w,i,0]=wp.max(0.,c.impulse[w,best])
    for g in range(p.manifold.count[w]):
        c.spin_hint[w,g]=0.
        pair=geom[p.manifold.first[w,g]];normal=p.manifold.frame[w,g][0]
        for old in range(c.group_count[w]):
            other=c.group_pairs[w,old]
            if pair[0]!=other[0] or pair[1]!=other[1]:continue
            if wp.dot(normal,c.group_normal[w,old])<.999 or wp.length_sq(p.manifold.center[w,g]-c.center[w,old])>.0004:continue
            for i in range(p.ncontact[w]):
                if p.manifold.contact_ids[w,i]==p.manifold.first[w,g]:
                    c.hint[w,i,1]=wp.dot(c.tangent[w,old],p.manifold.frame[w,g][1])
                    c.hint[w,i,2]=wp.dot(c.tangent[w,old],p.manifold.frame[w,g][2])
            c.spin_hint[w,g]=c.spin[w,old]
            break

@wp.kernel(enable_backward=False)
def save(p:ContactProblem,c:Cache,geom:wp.array(dtype=wp.vec2i),pos:wp.array(dtype=wp.vec3),frame:wp.array(dtype=wp.mat33),error:wp.array(dtype=int)):
    w=wp.tid();c.count[w]=0;c.group_count[w]=0
    if error[w]!=0:return
    c.count[w]=p.ncontact[w];c.group_count[w]=p.manifold.count[w]
    for i in range(p.ncontact[w]):
        ident=p.manifold.contact_ids[w,i]
        c.pairs[w,i]=geom[ident];c.pos[w,i]=pos[ident];c.normal[w,i]=frame[ident][0];c.impulse[w,i]=p.contact_impulse[w,i,0]
    for g in range(p.manifold.count[w]):
        c.group_pairs[w,g]=geom[p.manifold.first[w,g]];c.center[w,g]=p.manifold.center[w,g];c.group_normal[w,g]=p.manifold.frame[w,g][0]
        c.tangent[w,g]=wp.vec3(0.);c.spin[w,g]=p.manifold.impulse[w,g,2]
        for i in range(p.ncontact[w]):
            if p.manifold.contact_ids[w,i]==p.manifold.first[w,g]:
                c.tangent[w,g]=p.manifold.frame[w,g][1]*p.contact_impulse[w,i,1]+p.manifold.frame[w,g][2]*p.contact_impulse[w,i,2]

def adapter_class():
    from followup_candidates import ROOT,OUT,load
    from sequential_contact_adapter import SequentialContactAdapter
    source=(ROOT/'Labs/MimicKitTransfer/block_contact_gpu.py').read_text();cut=source.index('# Compatibility path')
    fast=source[:cut].replace('iterations:int,error:wp.array(dtype=int)):', 'iterations:int,error:wp.array(dtype=int),cache:Cache):',1)
    fast=fast.replace('for a in range(3):p.contact_impulse[w,c,a]=0.',
      'for a in range(3):\n                value=float(0.)\n                if wp.static(not retry):value=cache.hint[w,c,a]\n                p.contact_impulse[w,c,a]=value',1)
    fast=fast.replace('for g in range(p.manifold.count[w]):p.manifold.impulse[w,g,2]=0.',
      'for g in range(p.manifold.count[w]):\n                value=float(0.)\n                if wp.static(not retry):value=cache.spin_hint[w,g]\n                p.manifold.impulse[w,g,2]=value',1)
    path=OUT/'block_warm.py';path.write_text('from followup_warm_contacts import Cache\n'+fast+source[cut:]);module=load(path)
    class Warm(SequentialContactAdapter):
        def __init__(self,*args,**kw):
            super().__init__(*args,**kw);self.cache=allocate(self.data.nworld,self.capacity,self.data.qvel.device)
            self.block_kernel=module.make_block_iteration(self.p.nv,self.p.nmotor,warm_start=True)
            self.retry_block_kernel=module.make_block_iteration(self.p.nv,self.p.nmotor,warm_start=True,retry=True)
        def solve(self,m,d):
            original=wp.launch_tiled
            def launch(kernel,*a,**kw):
                if kernel==self.block_kernel:wp.launch(match,dim=d.nworld,inputs=[self.p,self.cache,d.contact.geom,d.contact.pos,d.contact.frame],device=d.qvel.device)
                if kernel in (self.block_kernel,self.retry_block_kernel):kw['inputs']=kw['inputs']+[self.cache]
                return original(kernel,*a,**kw)
            wp.launch_tiled=launch
            try:super().solve(m,d)
            finally:wp.launch_tiled=original
            wp.launch(save,dim=d.nworld,inputs=[self.p,self.cache,d.contact.geom,d.contact.pos,d.contact.frame,self.error],device=d.qvel.device)
    return Warm
