"""Create a portable, neutrally named handoff without training-source paths."""
import json, shutil
from pathlib import Path
import numpy as np
import torch
from prepare import OUT, ROOT, sha, atomic_json
OUT=ROOT/'Saved/RoboticMotionAE/20261019_mse_fullbody'


def main(destination=None, run_dir=None):
    run=run_dir or OUT/'run';completed=json.loads((run/'completed.json').read_text())
    config=json.loads((run/'config.json').read_text())
    width=config['hidden_dim'];depth=config['hidden_layers_per_side']
    architecture=' -> '.join(map(str,[405]+[width]*depth+[128]+[width]*depth+[405]))
    assert completed['state']=='complete'
    dest=Path(destination or ROOT/'Saved/MotionRegularizer');dest.mkdir(exist_ok=False)
    for name in ('motion_scorer.pt','autoencoder.pt'):shutil.copy2(run/name,dest/name)
    shutil.copy2(Path(__file__).with_name('features.py'),dest/'motion_features.py')
    shutil.copy2(ROOT/'Labs/MimicKitUEFN/humanoid_uefn.xml',dest/'robot.xml')
    manifest=json.loads((OUT/'data/dataset.json').read_text())
    meta=json.loads((ROOT/'Labs/MimicKitUEFN/limits.json').read_text())
    physics=json.loads((ROOT/'Labs/MimicKitUEFN/physics.json').read_text())
    schema=dict(schema=manifest['schema'],body_names=manifest['body_names'],input_dim=405,hz=30,window_poses=3,
        positions='Physical body origins, world-space metres, Z up',rotations='World-space proper 3x3 column-vector rotation matrices',
        ordering='time oldest to newest, body order, position XYZ then rotation column0 XYZ and column1 XYZ',
        origin='Oldest pelvis XY at ground height, fixed across all three poses',
        heading='Oldest pelvis local -X projected onto horizontal; projected +Y fallback below forward length .25',
        body_frames=meta['body_frames'],parents=meta['parents'],
        source_anchors={n:meta['groups'][n]['anchor'] for n in manifest['body_names']},
        body_local_com_m={n:physics['bodies'][n]['com'] for n in manifest['body_names']},
        model_sha256=sha(dest/'robot.xml'))
    atomic_json(dest/'body_contract.json',schema)
    validation=json.loads((run/'validation.json').read_text())
    # Numeric per-motion evidence without source labels, directories or provenance.
    for c in validation['clips']:c.pop('label',None)
    atomic_json(dest/'validation.json',validation)
    state=torch.load(run/'best.pt',map_location='cpu',weights_only=False)
    np.savez(dest/'normalization.npz',mean=state['mean'].numpy(),std=state['std'].numpy())
    raw=np.load(OUT/'data/clip_0_30hz.npz');data=np.load(OUT/'data/features.npz')
    ix=data['test_starts_0'][:4,None]+np.arange(3)[None,:]
    np.savez(dest/'example_windows.npz',positions=raw['position'][ix],rotations=raw['rotation'][ix])
    atomic_json(dest/'model_info.json',dict(name='Robotic Motion Regularizer',purpose='Regularize generated motion during noisy training',
        schema=manifest['schema'],architecture=architecture,
        hidden_blocks='Linear, LayerNorm, GELU; latent GELU; linear output',parameters=completed['parameters'],
        training_clips=completed['clip_count'],steps=completed['steps'],best_step=completed['best_step'],
        train_mse=completed['train_mse_at_best'],validation_mse=completed['best_validation'],test_mse=completed['test_mse'],
        split=manifest['split'],sampling=manifest['sampling'],validation_limit=manifest['validation_limit'],
        torch_version=torch.__version__,scorer_sha256=sha(dest/'motion_scorer.pt')))
    (dest/'smoke_test.py').write_text('''from pathlib import Path
import json
import numpy as np
import torch
from motion_features import encode

root=Path(__file__).resolve().parent
torch.set_num_threads(2)
model=torch.jit.load(str(root/'motion_scorer.pt'),map_location='cpu').eval()
for parameter in model.parameters():parameter.requires_grad_(False)
with np.load(root/'example_windows.npz') as d:
    p=torch.tensor(d['positions'],requires_grad=True)
    r=torch.tensor(d['rotations'])
x=encode(p,r,ground_height=0.)
cost=model(x)
cost.mean().backward()
assert cost.shape==(4,) and torch.isfinite(cost).all()
assert torch.isfinite(p.grad).all() and p.grad.abs().sum()>0
yaw=torch.tensor([[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]])
turned=encode((yaw@p.detach().unsqueeze(-1)).squeeze(-1)+torch.tensor([3.,-2.,0.]),yaw@r)
torch.testing.assert_close(x.detach(),turned,atol=3e-5,rtol=0.)
torch.testing.assert_close(model(turned),cost.detach(),atol=1e-5,rtol=1e-4)
print(json.dumps(dict(passed=True,costs=cost.detach().tolist(),finite_nonzero_position_gradient=True,heading_translation_invariance=True)))
''',encoding='utf-8')
    (dest/'README.md').write_text('''# Robotic Motion Regularizer

This frozen autoencoder supplies a short-horizon motion prior to help regularize
generated robotic motion during noisy training. Lower reconstruction cost means
the three-pose motion window is more familiar to the reference distribution.
It is ready to load; it has not been installed into any controller loss.

## Files

- `motion_scorer.pt`: portable TorchScript scoring module, including normalization.
- `autoencoder.pt`: raw TorchScript AE, mapping normalized features to normalized reconstruction.
- `motion_features.py`: exact differentiable feature encoder and architecture.
- `body_contract.json` and `robot.xml`: body order, frames, COM offsets and physical rig.
- `normalization.npz`: training mean/std for explicit raw-AE use.
- `model_info.json`, `validation.json`: architecture, metrics and measured limitations.
- `smoke_test.py`, `example_windows.npz`: executable CPU loading/gradient/invariance example.

Requires Python with PyTorch and NumPy. No project imports, simulator, SciPy or
source motion files are needed for scoring. Run `python smoke_test.py` in this
folder to check the installation. The training PyTorch version is in model_info.json.

## Input contract

Use THREE consecutive physical poses at 30 Hz: [t-2, t-1, t], spanning 1/15 s.
Positions are `[batch,3,15,3]`, rotations `[batch,3,15,3,3]`, float32, in the exact
body order in body_contract.json. Positions refer to BODY ORIGINS, not skeleton
joint markers or COM. Rotations are proper column-vector world rotation matrices.
The physical coordinate system is metres and Z up. Match the included physical
rig frames; skeleton joint quaternions are not interchangeable with body frames.
If the simulator gives COM positions, use `origin = com_position - R @ local_com`
with the supplied local COM offsets. If it uses another world basis, convert
both positions and orientations consistently before encoding; do not mirror one.

The encoder removes the oldest pelvis XY and only its heading, anchored at the
ground plane. This one upright reference frame stays FIXED for the entire window.
It preserves pelvis movement, absolute height above ground, and pitch/roll.
Rotating the whole window around world-up or translating it horizontally leaves
the score unchanged. Standing and lying remain distinguishable, without an
automatic preference for standing. Supply ground_height in the same world units.
For per-sample terrain heights, subtract each sample's ground Z from all its
poses first, then call with ground_height=0. Height must be fixed across a window.

Flattening is time, then body, then nine values: position XYZ and the first two
rotation-matrix COLUMNS (column0 XYZ, column1 XYZ). Use the supplied encoder
instead of hand-building features. Do not add velocity/controller/phase inputs.
Resample faster simulations at actual 30 Hz; do not supply three 60/240 Hz ticks.
Clear history on reset, teleport or discontinuous clip change and wait until
three valid poses exist. Never join history from different agents or episodes.

## Differentiable training use

```python
from pathlib import Path
import torch
from motion_features import encode

folder = Path(__file__).resolve().parent
ae = torch.jit.load(str(folder / "motion_scorer.pt"), map_location="cuda")
ae.eval()
for parameter in ae.parameters():
    parameter.requires_grad_(False)

# positions/rotations are differentiable GENERATED physical poses, same device.
features = encode(positions, rotations, ground_height=0.0)  # [B,405]
motion_cost = ae(features)                                # [B], unweighted
loss = existing_loss + ae_weight * motion_cost.mean()
loss.backward()
```

Freeze AE weights but keep gradients through its input and encoder. Do not wrap
the training score in no_grad or detach the current generated pose. Decide history
detachment according to your existing backpropagation horizon. Never score target
poses in place of generated poses. If the simulator is non-differentiable, this
cannot create pathwise policy gradients; use the cost as a reward term in the
existing RL estimator (negative sign) or through an existing differentiable model.

The scorer computes mean(((AE(z)-z)**2), features), with z=(features-mean)/std.
It expects UNNORMALIZED encoded features; do not normalize twice. Raw autoencoder.pt
expects z instead. The scorer itself contains the authoritative mean and std.

Start with a small ae_weight and calibrate against your existing losses and their
gradient magnitudes on representative clean and perturbed rollouts. Log raw and
weighted AE cost separately. The clean score percentiles in validation.json are
reference measurements, not termination thresholds. Keep your tracking/contact
losses; this module is an auxiliary prior and does not provide joint-limit or
collision enforcement. No hard rejection or universal weight is prescribed.

## Scope and validation

Architecture: ARCHITECTURE_DESCRIPTION. Latent dimension remains 128.
Training uses clean reference windows; perturbations are held out for scoring
checks, not added as reconstruction targets. Best weights are selected by
validation MSE; final test scores do not select the checkpoint.

The collection contains locomotion, idles and recovery motions.
Splits are chronological within each motion with frame gaps and no cross-boundary
windows. Short and periodic clips can yield very similar train/test poses. These
results do not establish generalization to unseen characters or motion families.
Per-motion diagnostics test 8cm temporal root jitter, a 10cm local body jump and
a mismatched final pose. See their measured success fractions; no universal
anomaly-detection claim is implied. A three-pose prior cannot judge long-horizon
timing or balance. It can assign low cost to some unnatural inputs and high cost
to valid unfamiliar motion, and reference reductions can contain contact/limit
imperfections. Validate the integrated regularizer on actual noisy rollouts.
''',encoding='utf-8')
    readme=dest/'README.md'
    readme.write_text(readme.read_text(encoding='utf-8').replace('ARCHITECTURE_DESCRIPTION',
        f'{depth} hidden layers of {width} neurons on each side'),encoding='utf-8')
    collection=json.loads((OUT/'collection.json').read_text())
    if collection.get('mse_clips'):
        verified=json.loads((OUT/'verification.json').read_text())
        atomic_json(dest/'reference_quality.json',dict(clips=64,diverse_references=12,omni=48,idle=2,getups=2,
            all_mse_targets_byte_identical=verified['all_mse_targets_byte_identical'],
            added_mse_foot_displacement_m=0.,upper_body_motion_verified=True,
            note='Exact full-body targets used by physical MSE training. No new projection, IK, foot correction or upper-body freezing.'))
        with (dest/'README.md').open('a',encoding='utf-8') as f:
            f.write('\nCurrent model was trained from fresh random weights on 64 motions: 12 diverse\n'
                    'references plus the exact 48 omni, 2 idle and 2 get-up physical MSE targets.\n'
                    'Both drawn/unarmed variants are included. The 52 MSE target files are\n'
                    'byte-identical to the deployed trainer: no new foot displacement or upper-body\n'
                    'freezing was introduced. Their original full-body articulation is preserved.\n'
                    'Sampling gives each family 50%, then chooses clips/windows uniformly.\n'
                    'Shortest loops have only one test window, so final-pose shuffle tests are\n'
                    'marked untested for those clips. This is not evidence of timing detection.\n')
            f.write(f"\nAt the selected checkpoint, normalized reconstruction MSE is "
                    f"{completed['train_mse_at_best']:.6f} on training, "
                    f"{completed['best_validation']:.6f} on validation, and "
                    f"{completed['test_mse']:.6f} on test. The substantial train/holdout gap "
                    "remains a limitation; training completion does not establish robust "
                    "generalization. Calibrate the prior on actual noisy rollouts.\n")
    else:
        atomic_json(dest/'reference_quality.json',dict(native_clips=462,
            native_foot_corrections=sum(r['foot_corrections'] for r in collection['native']),
            maximum_native_foot_vertical_correction_cm=max(r['max_lift_cm'] for r in collection['native']),
            maximum_native_body_origin_difference_cm=max(r['position_max_error_cm'] for r in collection['native']),
            note='Rejected broad native collection; do not deploy this model.'))
    # User requested neutral handoff vocabulary; inspect all portable payload bytes.
    for file in dest.iterdir():
        assert b'lafan' not in file.read_bytes().lower(),file.name
    atomic_json(dest/'checksums.json',{p.name:sha(p) for p in sorted(dest.iterdir()) if p.is_file()})
    print(str(dest),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--data-root',type=Path,default=OUT)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--run-dir',type=Path)
    args=parser.parse_args();OUT=args.data_root.resolve();main(args.output,args.run_dir.resolve() if args.run_dir else None)
