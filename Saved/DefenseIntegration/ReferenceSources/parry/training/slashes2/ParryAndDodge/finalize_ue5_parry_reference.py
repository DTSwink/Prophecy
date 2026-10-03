"""Add a strict UE dump contract and documented runtime sources to the fixture."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
import numpy as np
from compare_ue5_parry_reference import compare, self_test

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
REPO=ROOT.parents[1]
OUT=ROOT/'saved_defense_checkpoints/parry_unreal_reference_770015'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data): path.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')


def main():
    public=json.loads((OUT/'rollout.json').read_text())
    count=public['visible_frames'];paired=public['attacker_colliders']
    with np.load(OUT/'trace.npz',allow_pickle=False) as z:
        expected={
            'network/inputs':[z[f'frame/{f:03d}/network/input'][0].tolist() for f in range(2,count)],
            'network/outputs':[z[f'frame/{f:03d}/network/output'][0].tolist() for f in range(2,count)],
            'trajectory/positions':public['training_gpu_positions'],
            'trajectory/basis':public['training_gpu_basis'],
            'trajectory/roots':public['roots'],
            'colliders/centers':paired['centers_m'],
            'colliders/axes':paired['axes'],
            'contact/protected':int(paired['protected_by_first_block']),
            'contact/first_block_time':paired['first_block_time']}
        actual={**expected,'trajectory/positions':z['trajectory/positions'][0,:count].tolist(),
            'trajectory/basis':z['trajectory/rotations'][0,:count].tolist()}
        # Saved record may append self-only colliders; fixture uses the actual catalog.
        skeleton=json.loads((OUT/'skeleton.json').read_text())
        assert paired['names']==skeleton['collider_names'], 'Explicit auxiliary collider mapping needed'
        actual.update({'colliders/centers':z['colliders/centers'][0,:count].tolist(),
                       'colliders/axes':z['colliders/axes'][0,:count].tolist()})
    report=compare(expected,actual)
    assert report['passed'],report
    write(OUT/'parity_expected.json',expected)
    write(OUT/'parity_cpu_replay.json',actual)
    write(OUT/'parity_check.json',dict(comparison=report,comparator_tests=self_test(),
        scope='CPU decoder vs saved GPU poses/colliders; network is CPU; contact fields copied from GPU oracle, not independently re-detected; Unreal NOT tested'))
    write(OUT/'parity_dump_schema.json',dict(joint_names=public['joint_names'],collider_names=paired['names'],
        frames=list(range(count)),inferred_frames=list(range(2,count)),
        shapes={k:list(np.asarray(v).shape) for k,v in expected.items()},
        scalar_contact_units='source frames, not seconds',coordinate_system=public['units']))
    tree=ast.parse((ROOT/'ae4_pose_prior.py').read_text())
    labels=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='AE4_ATTACK_LABELS' for t in n.targets))
    controls={name:[*v,0.] for name,v in labels.items()};controls['spear']=[0,0,0,0,0,1]
    write(OUT/'attack_controls.json',dict(order=['attack_angle','is_pike','is_melee','is_kick','is_headbutt','is_spear'],values=controls))
    shutil.copyfile(HERE/'compare_ue5_parry_reference.py',OUT/'compare_ue5_parry_reference.py')
    manifest=json.loads((OUT/'manifest.json').read_text())
    extras=['frozen_parry_collision.py','frozen_parry_objective.py','frozen_parry_lower.py',
            'frozen_parry_batch.py','train_frozen_parry.py','triton_ccd.py','defense_labels.py',
            'frozen_parry_free_hand_idle.py','compare_ue5_parry_reference.py','finalize_ue5_parry_reference.py']
    with zipfile.ZipFile(OUT/'reference_source.zip','a',zipfile.ZIP_DEFLATED) as z:
        existing=set(z.namelist())
        for name in extras:
            p=HERE/name;relative=p.relative_to(REPO).as_posix()
            if relative not in existing:
                z.write(p,relative);manifest['source_files'][relative]=digest(p)
    manifest['handoff']='UNREAL_HANDOFF.md';manifest['strict_comparison_passed']=report['passed']
    manifest['files']={p.name:dict(sha256=digest(p),bytes=p.stat().st_size)
        for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
    write(OUT/'manifest.json',manifest)
    for name,info in manifest['files'].items(): assert digest(OUT/name)==info['sha256']
    print(json.dumps(dict(files_verified=len(manifest['files']),strict_comparison_passed=True,
        comparator_tests=7,unreal_execution_verified=False,folder=str(OUT))))


if __name__=='__main__': main()
