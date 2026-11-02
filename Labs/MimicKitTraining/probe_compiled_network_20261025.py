"""Bounded exactness screen of compiled checkpoint MLPs; production is untouched."""
import io, json, os, sys, time, traceback, zipfile
from pathlib import Path
ROOT = Path('/workspace/mimickit_trial')
OUT = ROOT / 'perf-lossless-20261024/compiled-network'
OUT.mkdir(exist_ok=True)
os.environ['TORCHINDUCTOR_COMPILE_THREADS'] = '1'
os.environ['TORCHINDUCTOR_CACHE_DIR'] = str(OUT / 'inductor-cache')
import torch


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    run = ROOT / 'runs' / sys.argv[1]
    backup = json.loads((run / 'backup_status.json').read_text())
    with zipfile.ZipFile(run / Path(backup['key']).name) as z:
        state = torch.load(io.BytesIO(z.read('model.pt')), map_location='cpu', weights_only=True)
    results = []
    for part, count in [('actor', 8192), ('critic', 4096)]:
        prefix = '_model._' + part + '_layers.'
        keys = sorted((k for k in state if k.startswith(prefix) and k.endswith('.weight')),
                      key=lambda k: int(k[len(prefix):].split('.')[0]))
        layers = []
        for key in keys:
            weight = state[key]
            layer = torch.nn.Linear(weight.shape[1], weight.shape[0])
            layer.weight.data.copy_(weight)
            layer.bias.data.copy_(state[key.replace('.weight', '.bias')])
            layers.extend([layer, torch.nn.ReLU()])
        model = torch.nn.Sequential(*layers).cuda()
        x = torch.randn((count, layers[0].in_features), device='cuda')
        target = torch.randn((count, layers[-2].out_features), device='cuda')

        def call(fn):
            model.zero_grad(set_to_none=True)
            y = fn(x)
            loss = (y * target).mean()
            loss.backward()
            return [y.detach().clone(), loss.detach().clone()] + [p.grad.clone() for p in model.parameters()]

        reference = call(model)
        start = time.perf_counter()
        compiled = torch.compile(model, fullgraph=True, dynamic=False, options={
            'epilogue_fusion': False, 'max_autotune': False,
            'triton.cudagraphs': False, 'shape_padding': False})
        actual = call(compiled)
        torch.cuda.synchronize()
        checks = [dict(equal=torch.equal(a, b), finite=bool(torch.isfinite(b).all()),
                       max_abs=float((a-b).abs().max()),
                       relative_l2=float((a-b).norm()/a.norm().clamp_min(1e-30)))
                  for a, b in zip(reference, actual)]
        result = dict(part=part, count=count, compile_and_first_call_seconds=time.perf_counter()-start,
                      checks=checks, equal=all(v['equal'] for v in checks))
        if result['equal']:
            timings = []
            for label in ['eager', 'compiled', 'compiled', 'eager'] * 2:
                fn = model if label == 'eager' else compiled
                call(fn)
                torch.cuda.synchronize()
                start = time.perf_counter()
                for _ in range(6):
                    call(fn)
                torch.cuda.synchronize()
                timings.append(dict(variant=label, seconds=(time.perf_counter()-start)/6))
            result['timings'] = timings
            result['timing_scope'] = 'Network-only, shared GPU; not a whole-training speedup.'
        results.append(result)
        (OUT/'progress.json').write_text(json.dumps(dict(checkpoint=backup, results=results), indent=2))
        print(json.dumps(result), flush=True)
    (OUT/'complete.json').write_text(json.dumps(dict(checkpoint=backup, results=results,
        precision='FP32 highest; TF32 disabled', production_changed=False,
        scope='Actual checkpoint feature MLPs with synthetic inputs; full PPO validation is still required for any passing candidate.'), indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc())
        raise
