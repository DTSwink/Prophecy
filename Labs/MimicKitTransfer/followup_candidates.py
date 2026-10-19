"""Isolated optimization candidates; production modules and live runs untouched."""
import importlib.util,sys,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Saved/MimicKitEquipment/optimization-followup'

def load(path):
    name='followup_'+path.stem
    if name in sys.modules:return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def generate():
    OUT.mkdir(exist_ok=True)
    original=(ROOT/'Labs/MimicKitTransfer/block_contact_gpu.py').read_text()
    cut=original.index('# Compatibility path')
    fast,tail=original[:cut],original[cut:]
    scratch=fast.replace('            wp.tile_cholesky_inplace(effective)',
        "            wp.tile_cholesky_inplace(effective)\n            scratch=wp.tile_zeros(shape=(nv,1),dtype=float,storage='shared')",1)
    for var,jac in [('response','jac'),('spin_response','spin_jac')]:
        old=f'{var}=wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose({jac})))'
        new=f'wp.tile_assign(scratch,wp.tile_transpose({jac}))\n'+(' '*20)+f'wp.tile_cholesky_solve_inplace(effective,scratch)\n'+(' '*20)+f'{var}=wp.tile_transpose(scratch)'
        # Contact-axis loop has twenty spaces; limit loop sixteen.
        scratch=scratch.replace('                    '+old,'                    '+new)
        new=new.replace('\n'+' '*20,'\n'+' '*16)
        scratch=scratch.replace('                '+old,'                '+new)
    (OUT/'block_scratch.py').write_text(scratch+tail)
    begin=fast.index('            for c in range(p.ncontact[w]):\n                for a in range(3):')
    end=fast.index('            for c in range(p.nlimit[w]):',begin)
    batch='''            for c in range(p.ncontact[w]):
                jac3=wp.tile_load(p.J[w,c],shape=(3,nv),storage='shared')
                response3=wp.tile_transpose(wp.tile_cholesky_solve(effective,wp.tile_transpose(jac3)))
                wp.tile_store(p.response[w,c],response3)
                for a in range(3):
                    jac_axis=wp.tile_view(jac3,offset=(a,))
                    response_axis=wp.tile_view(response3,offset=(a,))
                    if a==0:
                        p.effective_normal_diagonal[w,c]=wp.tile_extract(wp.tile_sum(wp.tile_map(multiply,jac_axis,response_axis)),0)
                    wp.tile_assign(v,v+wp.tile_reshape(response_axis,shape=(1,nv))*p.contact_impulse[w,c,a])
'''
    (OUT/'block_batch.py').write_text(fast[:begin]+batch+fast[end:]+tail)
    # Allocate only the active rows' zero entries; preserve every capacity and check.
    adapter=(ROOT/'Labs/MimicKitTransfer/sequential_contact_adapter.py').read_text()
    adapter=adapter.replace('p.ncontact.zero_();p.nlimit.zero_();p.limit_J.zero_(); p.J.zero_(); d.efc.force.zero_()',
                            'p.ncontact.zero_();p.nlimit.zero_(); d.efc.force.zero_()')
    adapter=adapter.replace('        speed=float(0.)','        for j in range(p.nv):p.limit_J[w,slot,j]=0.\n        speed=float(0.)',1)
    adapter=adapter.replace('    contactids[w,slot]=c','    for a in range(3):\n        for j in range(p.nv):p.J[w,slot,a,j]=0.\n    contactids[w,slot]=c',1)
    limits=(ROOT/'Labs/MimicKitTransfer/jolt_limit_directions.py').read_text().replace(
        '            for j in range(3):p.limit_J[w,slot,da+j]=gradient[j]',
        '            for j in range(p.nv):p.limit_J[w,slot,j]=0.\n            for j in range(3):p.limit_J[w,slot,da+j]=gradient[j]')
    (OUT/'limits_active.py').write_text(limits)
    adapter=adapter.replace('from jolt_limit_directions import append','from followup_limits_active import append')
    (OUT/'adapter_active.py').write_text(adapter)
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'Labs/MimicKitTransfer'/n for n in ('block_contact_gpu.py','sequential_contact_gpu.py','sequential_contact_adapter.py','contact_manifolds_gpu.py')]}
    (OUT/'baseline-hashes.json').write_text(json.dumps(hashes,indent=2))

def adapter_class(kind):
    generate()
    from sequential_contact_adapter import SequentialContactAdapter
    if kind=='baseline':return SequentialContactAdapter
    if kind=='active':
        load(OUT/'limits_active.py')
        return load(OUT/'adapter_active.py').SequentialContactAdapter
    module=load(OUT/('block_'+kind+'.py'))
    class Candidate(SequentialContactAdapter):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw)
            self.block_kernel=module.make_block_iteration(self.p.nv,self.p.nmotor,warm_start=True)
            self.retry_block_kernel=module.make_block_iteration(self.p.nv,self.p.nmotor,warm_start=True,retry=True)
    return Candidate

if __name__=='__main__':generate()
