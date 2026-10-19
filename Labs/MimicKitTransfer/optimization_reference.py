"""Load the hash-checked pre-optimization kernels for disposable comparisons."""
import hashlib,importlib.util,json,sys
from pathlib import Path


def components(folder=None):
    folder=Path(folder) if folder else Path(__file__).resolve().parents[2]/'Saved/MimicKitLocal/optimization/reference'
    hashes=json.loads((folder/'hashes.json').read_text(encoding='utf-8-sig'))
    def load(filename):
        path=folder/filename
        assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[filename]
        name='optimization_reference_'+hashlib.sha256(str(folder).encode()).hexdigest()[:8]+'_'+path.stem
        if name not in sys.modules:
            spec=importlib.util.spec_from_file_location(name,path)
            module=importlib.util.module_from_spec(spec);sys.modules[name]=module
            source=path.read_text()
            if filename=='contact_manifolds_gpu.py':
                # Share the current struct ABI, retaining all archived kernels.
                start=source.index('@wp.struct');end=source.index('def allocate(')
                binding='from contact_manifolds_gpu import ContactManifolds\n'
                padding='\n'*(source[start:end].count('\n')-binding.count('\n'))
                source=source[:start]+binding+padding+source[end:]
            if filename=='sequential_contact_adapter.py' and 'contact_manifolds_gpu.py' in hashes:
                manifold=load('contact_manifolds_gpu.py')
                source=source.replace('from contact_manifolds_gpu import prepare,replace_point_friction',
                    'from '+manifold.__name__+' import prepare,replace_point_friction')
            if filename in ('contact_manifolds_gpu.py','sequential_contact_adapter.py'):
                # The file hash above is checked before rebinding imports.
                exec(compile(source,str(path),'exec'),module.__dict__)
            else:spec.loader.exec_module(module)
        return sys.modules[name]
    import sequential_contact_gpu as current
    seed=load('sequential_contact_gpu.py')
    # The struct gained scratch arrays; the reference kernels never read them.
    seed.ContactProblem=current.ContactProblem;seed.friction_bound=current.friction_bound
    block=load('block_contact_gpu.py')
    projection=load('limit_projection_gpu.py')
    if 'sequential_contact_adapter.py' in hashes:
        SequentialContactAdapter=load('sequential_contact_adapter.py').SequentialContactAdapter
    else:
        from sequential_contact_adapter import SequentialContactAdapter
    class ReferenceAdapter(SequentialContactAdapter):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.iterate_kernel=seed.make_tiled_iteration(self.p.nv,self.p.nmotor)
            self.fallback_kernel=seed.make_tiled_iteration(self.p.nv,self.p.nmotor,fallback=True)
            self.block_kernel=block.make_block_iteration(self.p.nv,self.p.nmotor)
    return ReferenceAdapter,projection.SplitLimitProjection


def configure_candidate(seed_iterations=None):
    """Test-only construction override; never modifies a running simulation."""
    import contact_engine
    original=contact_engine.SequentialContactAdapter
    class CandidateAdapter(original):
        def __init__(self,*args,**kwargs):
            if seed_iterations is not None:kwargs['seed_iterations']=seed_iterations
            super().__init__(*args,**kwargs)
    contact_engine.SequentialContactAdapter=CandidateAdapter
