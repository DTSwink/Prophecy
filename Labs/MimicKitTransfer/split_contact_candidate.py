"""Separate factorization scratch from the long warm contact sweep.

Same equations, ordering, tolerances and fallback. The factor matrix no longer
occupies shared memory while a warp iterates over contacts.
"""
from pathlib import Path
import importlib.util,sys,textwrap

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitTransfer/getup-transfer-20261023'

def generate(source_path=None):
    source=(source_path or ROOT/'Labs/MimicKitTransfer/block_contact_gpu.py').read_text()
    prefix=source[:source.index('def make_block_iteration')]
    prepare=source[source.index('        v=wp.tile_load(p.velocity'):source.index('            # Exactly one warp')]
    prepare=prepare[:prepare.index('        converged=bool(False)')]+prepare[prepare.index('            wp.tile_assign(effective'):]
    # Remove one outer-loop indent; the incoming warm branch is solved once.
    i=prepare.index('            wp.tile_assign(effective')
    prepare=prepare[:i]+textwrap.indent(textwrap.dedent(prepare[i:]),'        ')
    begin=prepare.index('            request=');end=prepare.index('            active[0,a]=status',begin)
    prepare=prepare[:begin]+'            status=p.warm_status[w,a]\n'+prepare[end:]
    prepare=prepare.replace("        guess=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')\n        wp.tile_assign(guess,v)\n",'')
    prepare=prepare.replace("        active=wp.tile_zeros(shape=(1,nmotor),dtype=int,storage='shared')\n",'').replace('            active[0,a]=status\n','')
    loop=source[source.index('            k0=lane'):source.index('            changed=bool(False)')]
    loop=textwrap.indent(textwrap.dedent(loop),'        ')
    loop=loop.replace('wp.tile_extract(v,0,wp.min(k0,nv-1))','p.velocity[w,wp.min(k0,nv-1)]').replace('wp.tile_extract(v,0,wp.min(k1,nv-1))','p.velocity[w,wp.min(k1,nv-1)]')
    loop=loop[:loop.index('        wp.tile_assign(v,')]
    finish='''        changed=bool(False);defect=float(0.)
        for a in range(nmotor):
            speed=p.velocity[w,p.dofs[a]];cap=dt*p.caps[a]
            request=dt*p.gains[a]*(p.commands[w,a]-speed)
            status=int(0)
            if request>cap:status=1
            elif request< -cap:status=-1
            old_status=p.warm_status[w,a]
            if status!=old_status:changed=True
            impulse=request
            if old_status!=0:impulse=float(old_status)*cap
            if lane==0:p.motor_impulse[w,a]=impulse
            defect=wp.max(defect,wp.abs(impulse-wp.clamp(request,-cap,cap))/dt)
        if lane==0:
            p.stats[w,0]=defect
            if changed:p.warm_state[w]=-1
            else:p.warm_state[w]=2
'''
    code=prefix+'''def make_split(nv,nmotor):
    @wp.kernel(module='unique',enable_backward=False)
    def prepare(p:ContactProblem,mass:wp.array3d(dtype=float)):
        w,lane=wp.tid();dt=p.dt[0]
        if p.warm_state[w]<=0:return
'''+prepare+'''        velocity_out=p.velocity
        wp.tile_store(velocity_out,v,offset=(w,0))
    @wp.kernel(module='unique',enable_backward=False)
    def sweep(p:ContactProblem,iterations:int):
        w,lane=wp.tid();dt=p.dt[0]
        if p.warm_state[w]<=0:return
'''+loop+finish+'''    return prepare,sweep
'''
    path=OUT/'split_contact_generated.py';path.write_text(code)
    fallback=source.replace('                warm=p.warm_state[w]>0','                if p.warm_state[w]!=0:return\n                warm=False',1)
    fallback_path=OUT/'split_contact_fallback.py';fallback_path.write_text(fallback)
    return path,fallback_path

def load(path):
    spec=importlib.util.spec_from_file_location(path.stem,path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def install(engine):
    import warp as wp
    p=engine.transfer_contact;path,fallback=generate()
    prepare,sweep=load(path).make_split(p.p.nv,p.p.nmotor)
    p.block_kernel=load(fallback).make_block_iteration(p.p.nv,p.p.nmotor,warm_start=True)
    original=wp.launch_tiled
    def launch(kernel,*args,**kwargs):
        if kernel is p.block_kernel:
            original(prepare,dim=engine.get_num_envs(),inputs=[p.p,engine._solver.mjw_data.qM],block_dim=32,device=engine._device)
            original(sweep,dim=engine.get_num_envs(),inputs=[p.p,p.iterations],block_dim=32,device=engine._device)
        return original(kernel,*args,**kwargs)
    wp.launch_tiled=launch
    try:engine._build_graphs()
    finally:wp.launch_tiled=original
    return prepare,sweep

def generate_full():
    source=(ROOT/'Labs/MimicKitTransfer/block_contact_gpu.py').read_text()
    prefix=source[:source.index('def make_block_iteration')]
    prepare=source[source.index('            wp.tile_assign(effective'):source.index('            # Exactly one warp')]
    prepare=textwrap.indent(textwrap.dedent(prepare),'        ')
    prepare=prepare.replace('if warm and outer==0:', 'if work.warm[w]!=0 and work.outer[w]==0:')
    prepare=prepare.replace('active[0,a]=status','work.status[w,a]=status')
    loop=source[source.index('            k0=lane'):source.index('            changed=bool(False)')]
    loop=textwrap.indent(textwrap.dedent(loop),'        ')
    loop=loop.replace('wp.tile_extract(v,0,wp.min(k0,nv-1))','p.velocity[w,wp.min(k0,nv-1)]').replace('wp.tile_extract(v,0,wp.min(k1,nv-1))','p.velocity[w,wp.min(k1,nv-1)]')
    loop=loop[:loop.index('        wp.tile_assign(v,')]
    finish=source[source.index('            changed=bool(False)'):source.index('            p.stats[w,0]=defect')]
    finish=textwrap.indent(textwrap.dedent(finish),'        ').replace('wp.tile_extract(v,0,p.dofs[a])','p.velocity[w,p.dofs[a]]').replace('wp.tile_extract(active,0,a)','work.status[w,a]')
    code=prefix+'''@wp.struct
class Work:
    guess:wp.array2d(dtype=float)
    status:wp.array2d(dtype=int)
    active:wp.array(dtype=int)
    warm:wp.array(dtype=int)
    outer:wp.array(dtype=int)

def make_full(nv,nmotor,retry=False):
    @wp.kernel(module='unique',enable_backward=False)
    def begin(p:ContactProblem,work:Work):
        w,lane=wp.tid()
        enabled=True
        if wp.static(retry):enabled=p.warm_state[w]==-1
        if lane==0:
            work.active[w]=int(enabled);work.warm[w]=int(p.warm_state[w]>0);work.outer[w]=0
        if not enabled:return
        for k in range(lane,nv,32):work.guess[w,k]=p.velocity[w,k]
        for c in range(lane,p.ncontact[w],32):
            for a in range(3):p.contact_impulse[w,c,a]=0.
        for c in range(lane,p.nlimit[w],32):p.limit_impulse[w,c]=0.
        if p.manifold.enabled:
            for g in range(lane,p.manifold.count[w],32):p.manifold.impulse[w,g,2]=0.
    @wp.kernel(module='unique',enable_backward=False)
    def prepare(p:ContactProblem,mass:wp.array3d(dtype=float),work:Work):
        w,lane=wp.tid();dt=p.dt[0]
        if work.active[w]==0:return
        guess=wp.tile_load(work.guess,shape=(1,nv),offset=(w,0))
        free_velocity=wp.tile_load(p.free,shape=(1,nv),offset=(w,0))
        effective=wp.tile_load(mass[w],shape=(nv,nv),storage='shared')
        momentum=wp.tile_matmul(free_velocity,effective)
        v=wp.tile_zeros(shape=(1,nv),dtype=float,storage='shared')
'''+prepare+'''        velocity_out=p.velocity
        wp.tile_store(velocity_out,v,offset=(w,0))
    @wp.kernel(module='unique',enable_backward=False)
    def sweep(p:ContactProblem,iterations:int,error:wp.array(dtype=int),work:Work):
        w,lane=wp.tid();dt=p.dt[0]
        if work.active[w]==0:return
'''+loop+finish+'''        if lane==0:p.stats[w,0]=defect
        if not changed:
            if lane==0:work.active[w]=0;p.warm_state[w]=1
            for a in range(lane,nmotor,32):p.warm_status[w,a]=work.status[w,a]
            return
        if work.warm[w]!=0:
            if lane==0:work.active[w]=0;p.warm_state[w]=-1
            return
        for k in range(lane,nv,32):work.guess[w,k]=(work.guess[w,k]+p.velocity[w,k])*.5
        if lane==0:
            work.outer[w]+=1
            if work.outer[w]>=60:
                work.active[w]=0;p.warm_state[w]=0
                if error[w]==0:error[w]=5
    return begin,prepare,sweep
'''
    path=OUT/'split_full_generated.py';path.write_text(code);return path

def install_full(engine):
    import warp as wp
    p=engine.transfer_contact;module=load(generate_full());n=engine.get_num_envs();dev=engine._device
    work=module.Work();work.guess=wp.zeros((n,p.p.nv),dtype=float,device=dev);work.status=wp.zeros((n,p.p.nmotor),dtype=int,device=dev)
    for name in ('active','warm','outer'):setattr(work,name,wp.zeros(n,dtype=int,device=dev))
    kernels={p.block_kernel:module.make_full(p.p.nv,p.p.nmotor),p.retry_block_kernel:module.make_full(p.p.nv,p.p.nmotor,retry=True)}
    original=wp.launch_tiled
    def launch(kernel,*args,**kwargs):
        if kernel in kernels:
            begin,prepare,sweep=kernels[kernel]
            original(begin,dim=n,inputs=[p.p,work],block_dim=32,device=dev)
            for _ in range(60):
                original(prepare,dim=n,inputs=[p.p,engine._solver.mjw_data.qM,work],block_dim=32,device=dev)
                original(sweep,dim=n,inputs=[p.p,p.iterations,p.error,work],block_dim=32,device=dev)
            return
        return original(kernel,*args,**kwargs)
    wp.launch_tiled=launch
    try:engine._build_graphs()
    finally:wp.launch_tiled=original
    engine._split_contact_work=work
    return kernels

if __name__=='__main__':print(generate())
