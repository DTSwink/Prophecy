"""Export the exact frozen lab recurrence to native, single-agent ONNX graphs.

Only this build-time tool uses PyTorch. The game runs the graphs through NNE.
All coordinates remain the lab's metres/Y-up matrices until the native boundary.
"""
import hashlib
import argparse
import faulthandler
import json
import sys
import time
import warnings
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'Labs/BodyflipLab'))
sys.path.insert(0, str(PROJECT / 'Saved/Diagnostics/BodyflipPort20261030/python'))
from resume_locomotion import ResumeLocomotion, PolicyStep, encode_lower
from locomotion import torch, runtime_data, upper_data, upper_ctl, cached_data

OUT = PROJECT / 'Content/BodyflipLab/NN'
OUT.mkdir(parents=True, exist_ok=True)
import onnx
import onnxruntime as ort


class Seeds(torch.nn.Module):
    def __init__(self, owner, mode, basis, heading):
        super().__init__()
        self.runtime, self.mode = owner.runtime, mode
        self.basis, self.heading = basis, heading

    def forward(self, packed):
        r, m, basis, heading = self.runtime, self.mode, self.basis, self.heading
        p = packed[:, :150].reshape(2, 25, 3)
        q = packed[:, 150:600].reshape(2, 25, 3, 3)
        roots = packed[:, 600:606].reshape(2, 3)
        lower = encode_lower(r.lower_clip, p, q, roots, basis.expand(2, -1, -1))
        upper = upper_data.upper_state_from_global_pose_and_heading(
            r.full_by_mode[m], p, q, roots, heading.expand(2, -1, -1))
        previous, current = lower.split(1)
        prev_upper, cur_upper = upper.split(1)
        prev_pelvis = runtime_data.pelvis_heading_features(previous, basis, heading)
        cur_pelvis = runtime_data.pelvis_heading_features(current, basis, heading)
        base = runtime_data.base_upper_from_lower(current, roots[1:2], basis, heading,
            r.full_by_mode[m], r.rest_offsets_by_mode[m][0:1])
        return torch.cat((previous, current, prev_upper, cur_upper, prev_pelvis, cur_pelvis, base), -1)


class Step(torch.nn.Module):
    def __init__(self, owner, mode, basis, heading):
        super().__init__()
        self.step = PolicyStep(owner, mode, basis, heading)
        self.runtime, self.mode, self.basis, self.heading = owner.runtime, mode, basis, heading

    def forward(self, packed):
        prev, cur, pu, cu, pp, base, root, nxt, features = torch.split(
            packed, [41, 41, 90, 90, 9, 90, 3, 3, 35], dim=-1)
        lower, upper, pelvis, next_base = self.step(prev, cur, pu, cu, pp, base, root, nxt, features)
        p, q = upper_ctl.decode_rows(self.runtime, self.mode, lower, upper, pelvis,
            nxt, self.basis, self.heading, torch.zeros(1, dtype=torch.long))
        return torch.cat((lower, upper, pelvis, next_base, p.reshape(1, -1), q.reshape(1, -1)), -1)


@torch.inference_mode()
def initial_bank(owner, mode):
    """Two NN poses per gait phase, sufficient to seed fresh live recurrence."""
    r = owner.runtime
    if owner.cache is None:
        payload = cached_data.build_category_cache(r, owner.lower_path, maximum_k=120)
        owner.cache = cached_data.CachedLowerCategory(payload, r, owner.lower_path, owner.device)
    cache, full = owner.cache, r.full_by_mode[mode]
    stride = 19 if owner.gait == 'run' else 29
    ids, gaze = torch.zeros(1, dtype=torch.long), torch.zeros(1, 2)
    def gather(name, i):
        return cache.gather(name, ids, torch.tensor([i]))
    def base(i):
        return cache.base_upper(mode, ids, torch.tensor([i]))
    offsets = r.full_geometry_by_mode[mode]['local_offsets'][0:1]
    lengths = r.full_geometry_by_mode[mode]['ik_limb_lengths'][0:1]
    result = []
    for phase in range(stride + 1):
        start, rows, roots = 60 + phase, [], []
        warm = start - stride
        previous, current = runtime_data.upper_overlay_runtime_rows(r, mode,
            ids.repeat(2), torch.tensor([warm - 1, warm]), gaze.repeat(2, 1), owner.device).split(1)
        for i in range(warm, start + 1):
            if i > warm:
                k = i - 1
                prior = upper_data.clean_upper_state(base(i) + current - base(k))
                inp = torch.cat((previous, prior, gather('pelvis_heading', k - 1),
                    gather('pelvis_heading', k), gather('pelvis_heading', i),
                    gather('root_features', k), torch.full((1, 1), mode),
                    gather('feet_heading', k), gather('feet_heading', i), gaze), -1)
                following = upper_data.clean_upper_state(prior + owner.agent(inp))
                following = upper_ctl.clamp_viewer_forearm_lengths(full, following,
                    gather('pelvis_heading', i), offsets, lengths)
                previous, current = current, following
            if i < start - 1:
                continue
            p, q = upper_ctl.decode_rows(r, mode, gather('lower_vector', i), current,
                gather('pelvis_heading', i), gather('root_position', i),
                gather('root_rotation', i), gather('heading', i), ids)
            rows.append(dict(points=p[0].tolist(), axes=q[0].tolist()))
            roots.append(gather('root_position', i)[0].tolist())
        origin = torch.tensor(roots[1])
        for row in rows:
            row['points'] = (torch.tensor(row['points']) - origin).tolist()
        roots = (torch.tensor(roots) - origin).tolist()
        result.append(dict(seeds=rows, roots=roots))
    return dict(stride=stride, names=list(full.body_names), phases=result)


def progress(label):
    print(time.strftime('%H:%M:%S'), label, flush=True)


def export_graph(model, sample, path):
    begin = time.perf_counter()
    progress('ONNX trace begin ' + path.name)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        # The lower-only policy has zero core-joint channels. PyTorch's legacy
        # ONNX reshape symbolic treats literal zero as "copy input dimension",
        # which is wrong for these empty tensors. Materialize an exact empty
        # constant when the traced output shape is known, eliminating no data.
        from torch.onnx._internal.torchscript_exporter import symbolic_helper as sh
        reshape = sh._reshape_helper
        def exact_reshape(g, value, shape, allowzero=0):
            sizes = sh._maybe_get_const(shape, 'is')
            before = sh._get_tensor_sizes(value)
            if isinstance(sizes, (list, tuple)):
                sizes = list(sizes)
                if before is not None and 0 in before and sizes.count(-1) == 1:
                    sizes[sizes.index(-1)] = 0
                if 0 in sizes and all(isinstance(n, int) and n >= 0 for n in sizes):
                    dtype = sh._type_utils.JitScalarType.from_value(value).dtype()
                    return g.op('Constant', value_t=torch.empty(sizes, dtype=dtype))
            return reshape(g, value, shape, allowzero)
        sh._reshape_helper = exact_reshape
        try:
            torch.onnx.export(model.eval(), sample, str(path), input_names=['input'],
                output_names=['output'], opset_version=17, do_constant_folding=True,
                dynamo=False)
        finally:
            sh._reshape_helper = reshape
    progress(f'ONNX trace end {path.name}: {time.perf_counter()-begin:.2f}s, {path.stat().st_size} bytes')
    onnx.checker.check_model(str(path))
    progress('ONNX check passed ' + path.name)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(path), options, providers=['CPUExecutionProvider'])
    progress('ORT session ready ' + path.name)
    return session


def packed_seed(bank):
    x = bank['phases'][0]
    return torch.cat((torch.tensor([s['points'] for s in x['seeds']]).reshape(1, -1),
        torch.tensor([s['axes'] for s in x['seeds']]).reshape(1, -1),
        torch.tensor(x['roots']).reshape(1, -1)), -1)


@torch.inference_mode()
def main(profiles=None):
    receipt = {'schema': 1, 'seedInput': 606, 'seedOutput': 370,
        'stepInput': 402, 'stepOutput': 530, 'graphs': {}}
    old_receipt = OUT / 'Receipt.json'
    if profiles and old_receipt.exists():
        receipt['graphs'].update(json.loads(old_receipt.read_text()).get('graphs', {}))
    for gait in ('run', 'walk'):
        if profiles and not any(p.startswith(gait+'-') for p in profiles):
            continue
        progress('Loading original frozen policies ' + gait)
        owner = ResumeLocomotion(gait)
        owner.runtime.install_policy()
        _, basis, heading = runtime_data.root_state(owner.runtime, torch.zeros(1, dtype=torch.long))
        store = owner.runtime.store
        for mode, name in ((-1., 'unarmed'), (1., 'drawn')):
            stem = gait + '-' + name
            if profiles and stem not in profiles:
                continue
            progress('Building phase seeds ' + stem)
            bank = initial_bank(owner, mode)
            bank.update(maxSpeedScale=float(store.cfg.max_speed_scale_final),
                heading=heading[0].tolist(), fps=30, gait=gait)
            (OUT / (stem + '-seeds.json')).write_text(json.dumps(bank, separators=(',', ':')))
            encoder = Seeds(owner, mode, basis, heading).eval()
            seed = packed_seed(bank)
            seed_session = export_graph(encoder, seed, OUT / (stem + '-seed.onnx'))
            state = encoder(seed)
            progress('Validating seed graph ' + stem)
            torch.testing.assert_close(torch.tensor(seed_session.run(None, {'input': seed.numpy()})[0]), state, rtol=2e-5, atol=3e-6)
            prev, cur, pu, cu, pp, cp, base = torch.split(state, [41,41,90,90,9,9,90], dim=-1)
            velocity = torch.tensor(bank['phases'][0]['roots'][1]) - torch.tensor(bank['phases'][0]['roots'][0])
            root = torch.zeros(1, 3)
            features = torch.zeros(1, 35)
            features[0, :2] = (velocity @ heading[0])[[0, 2]] / store.cfg.max_speed_scale_final
            for k in range(8):
                features[0, 3 + 4*k:5 + 4*k] = features[0, :2].clamp(-2, 2)
                features[0, 5 + 4*k] = 1
            packed = torch.cat((prev,cur,pu,cu,pp,base,root,root+velocity,features), -1)
            step = Step(owner, mode, basis, heading).eval()
            session = export_graph(step, packed, OUT / (stem + '-step.onnx'))
            progress('Validating recurrent graph ' + stem)
            maximum = 0.
            for frame in range(45):
                expected = step(packed)
                actual = torch.tensor(session.run(None, {'input': packed.numpy()})[0])
                maximum = max(maximum, float((actual - expected).abs().max()))
                torch.testing.assert_close(actual, expected, rtol=4e-4, atol=2e-5)
                lower, upper, pelvis, next_base, _, _ = torch.split(actual, [41,90,9,90,75,225], -1)
                prev, cur, pu, cu, pp, base = cur, lower, cu, upper, cp, next_base
                cp = pelvis
                root = root + velocity
                packed = torch.cat((prev,cur,pu,cu,pp,base,root,root+velocity,features), -1)
            receipt['graphs'][stem] = {'framesChecked':45,'maxAbsoluteError':maximum}
            receipt['graphs'][stem]['sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (OUT/(stem+'-seed.onnx'), OUT/(stem+'-step.onnx'), OUT/(stem+'-seeds.json'))}
            print(stem, receipt['graphs'][stem], flush=True)
    receipt['sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in ('.onnx','.json') and p.name!='Receipt.json'}
    (OUT / 'Receipt.json').write_text(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profiles', help='Comma-separated profile names for a bounded diagnostic export')
    args = parser.parse_args()
    if args.profiles and any(p not in ('run-unarmed', 'run-drawn', 'walk-unarmed', 'walk-drawn') for p in args.profiles.split(',')):
        parser.error('Unknown profile')
    faulthandler.enable()
    faulthandler.dump_traceback_later(90, repeat=True)
    try:
        main(args.profiles.split(',') if args.profiles else None)
    finally:
        faulthandler.cancel_dump_traceback_later()
