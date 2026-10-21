"""Package the authorized perturbation continuation without renting a GPU."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile
import numpy as np
import torch
import yaml
from uefn_package import runtime_files

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'Saved/MimicKitEquipment/perturbed-preparation'
BUNDLE = ROOT/'Exports/MimicKitEquipment/20261019_stopped_47039'
AE = ROOT/'Saved/MotionRegularizer-2x512'


def main():
    torch.set_num_threads(1)
    from scipy.spatial.transform import Rotation
    with zipfile.ZipFile(BUNDLE/'training_source.zip') as z:
        files = {n: z.read(n) for n in z.namelist()}
    cp = BUNDLE/'checkpoint_0047039_final.zip'
    manifest = json.loads((BUNDLE/'manifest.json').read_text())
    if hashlib.sha256(cp.read_bytes()).hexdigest() != manifest['checkpoint']['sha256']:
        raise ValueError('Preserved checkpoint checksum mismatch')
    checksums = json.loads((AE/'checksums.json').read_text())
    for name in ('motion_scorer.pt', 'motion_features.py', 'body_contract.json', 'robot.xml'):
        if hashlib.sha256((AE/name).read_bytes()).hexdigest() != checksums[name]:
            raise ValueError('AE portable bundle changed: '+name)
    spec = importlib.util.spec_from_file_location('prior_features', AE/'motion_features.py')
    feature = importlib.util.module_from_spec(spec);spec.loader.exec_module(feature)
    scorer = torch.jit.load(str(AE/'motion_scorer.pt'), map_location='cpu').eval()
    with zipfile.ZipFile(cp) as z:
        replay = np.load(io.BytesIO(z.read('replay.npz')))
        metadata = json.loads(str(replay['metadata']))
        costs, tracking = [], []
        by_row = []
        for i, row in enumerate(metadata['replay_rows']):
            suffix = '' if i == 0 else '_'+str(i)
            pose = replay['pose'+suffix]
            if len(pose) < 3:
                continue
            p = torch.tensor(np.stack([pose[j:j+3, :, :3] for j in range(len(pose)-2)]))
            matrices = Rotation.from_quat(pose[:, :, 3:].reshape(-1, 4)).as_matrix().astype(np.float32).reshape(len(pose), 15, 3, 3)
            r = torch.tensor(np.stack([matrices[j:j+3] for j in range(len(pose)-2)]))
            with torch.no_grad():
                cost = scorer(feature.encode(p, r))
            terms = replay['loss_terms'+suffix]
            names = row['loss_term_names']
            columns = [j for j, name in enumerate(names) if name in ('position_mse','linear_velocity_mse','rotation_mse','angular_velocity_mse','pelvis_velocity_extra')]
            mse = terms[2:, columns].sum(-1)
            costs.extend(cost.tolist());tracking.extend(mse.tolist())
            by_row.append(dict(world=row['world'], frames=len(cost), raw_ae_mean=float(cost.mean()), weighted_tracking_mean=float(mse.mean())))
    weight = float(np.mean(tracking)/np.mean(costs))
    if not np.isfinite(weight) or weight <= 0:
        raise ValueError('Invalid AE calibration')
    calibration = dict(checkpoint_sha256=manifest['checkpoint']['sha256'], windows=len(costs),
        mean_raw_ae=float(np.mean(costs)), mean_weighted_tracking=float(np.mean(tracking)),
        ae_weight=weight, rule='Match mean existing weighted body tracking cost on latest checkpoint recorded rollouts; excludes flat COM and supervised auto-phase', rows=by_row)
    (OUT/'ae_calibration.json').write_text(json.dumps(calibration, indent=2))
    for name, path in runtime_files(ROOT).items():
        if name.startswith('assets/') and name in files and path.suffix in ('.xml', '.json') and files[name] != path.read_bytes():
            raise ValueError('Workspace physical asset differs from preserved checkpoint; do not silently replace '+name)
        files[name] = path.read_bytes()
    for name in ('dashboard.py','telemetry.py','bridge.py','replay.py','preflight_perturbed.py'):
        path = Path(__file__).with_name(name)
        if path.exists():files['pipeline/'+name] = path.read_bytes()
    for name in ('motion_scorer.pt','motion_features.py','body_contract.json','robot.xml','model_info.json','README.md'):
        files['assets/motion_prior/'+name] = (AE/name).read_bytes()
    files['prepared/com2_targets.json'] = (OUT/'com2_targets.json').read_bytes()
    files['prepared/ae_calibration.json'] = (OUT/'ae_calibration.json').read_bytes()
    cfg = yaml.safe_load(files['prepared/env_config.yaml'])
    cfg['idle_row_fraction'] = .3
    cfg['perturbed_motion'] = dict(fraction=.7, yaw_degrees=90., grace_ticks=8,
        min_speed_ratio=.7, max_speed_ratio=1.7, angle_degrees=45.,
        ae_ticks=80, blend_ticks=60, getup_ticks=180, getup_head_reset_fraction=.9,
        getup_head_height_weight=1., getup_start_frame=0,
        ae_weight=weight/10, ae_directory='/workspace/mimickit_trial/assets/motion_prior',
        com2_targets='/workspace/mimickit_trial/prepared/com2_targets.json',
        phase='prior prediction input and current target; no supervision on autoregressive rows',
        getup_pose='random local pose across all locomotion frames; original pelvis and velocities',
        getup_objective='AE plus squared head-height shortfall after tick60; no body or COM tracking MSE',
        getup_reset='head above 90 percent of assigned idle frame0 head height, or 180 ticks; bootstrap reset, no penalty',
        auxiliary='No flat-COM loss on perturbed rows; auto-phase supervision only on clock-input rows',
        normal='unchanged except idle fraction .3')
    files['prepared/env_config.yaml'] = yaml.safe_dump(cfg, sort_keys=False).encode()
    source = OUT/'source.zip'
    with zipfile.ZipFile(source, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():z.writestr(name, data)
    # Expand only preparation/runtime files needed by the local smoke. Never
    # overwrite Unreal assets or any old checkpoint's source package.
    local = OUT/'source'
    for name, data in files.items():
        if name.startswith(('assets/','prepared/','pipeline/')):
            p = local/name;p.parent.mkdir(parents=True, exist_ok=True);p.write_bytes(data)
    for p in (local/'prepared').glob('*.yaml'):
        p.write_text(p.read_text(encoding='utf-8').replace('/workspace/mimickit_trial',local.as_posix()), encoding='utf-8')
    receipt = dict(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        bytes=source.stat().st_size, checkpoint=dict(manifest['checkpoint'],local=str(cp)),
        ae_calibration=calibration, prepared_config=cfg, launched=False)
    (OUT/'prepared.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(dict(bytes=receipt['bytes'], ae_weight=weight, windows=len(costs), source_sha256=receipt['source_sha256'])))


if __name__ == '__main__':main()
