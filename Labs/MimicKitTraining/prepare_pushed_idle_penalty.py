"""Patch the pinned locomotion runtime: pushed idle FAIL costs 100, once."""
import ast
import hashlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace
import torch
import yaml
import deploy_locomotion_branch as d

OUT = d.OUT / 'pushed-idle-penalty'

def prepare():
    OUT.mkdir(exist_ok=True)
    plan = json.loads((d.OUT / 'final-phase-prepared.json').read_text())
    (OUT / 'previous-plan.json').write_text(json.dumps(plan, indent=2))
    with zipfile.ZipFile(plan['source']['local']) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    edits = {
        'perturbed_omni.py': (
            '        if self._mode == EnvMode.TRAIN:\n            # Per-world counters only;',
            "        idle_penalty = float(self._perturb_cfg.get('pushed_idle_failure_penalty', 0.))\n"
            "        if idle_penalty and hasattr(self, '_final'):\n"
            "            idle_failed = self._final.minus & (self._done_buf == DoneFlags.FAIL.value)\n"
            "            self._reward_buf.sub_(idle_failed.to(self._reward_buf.dtype) * idle_penalty)\n"
            '        if self._mode == EnvMode.TRAIN:\n            # Per-world counters only;'),
        'final_locomotion.py': (
            'target_termination_bodies=[],sphere_only=False)',
            "target_termination_bodies=[],sphere_only=False,pushed_idle_failure_penalty=float(self.env._perturb_cfg.get('pushed_idle_failure_penalty',0.)))"),
        'replay.py': (
            "            expected-=float(meta.get('normal_getup_failure_penalty',0.))*(data[1:,0]==1)",
            "            expected-=float(meta.get('normal_getup_failure_penalty',0.))*(data[1:,0]==1)\n"
            "            expected-=float(meta.get('pushed_idle_failure_penalty',0.))*(data[1:,0]==1)")}
    for name, (old, new) in edits.items():
        key = 'pipeline/' + name
        source = entries[key].decode()
        assert source.count(old) == 1, name
        entries[key] = source.replace(old, new).encode()
        compile(entries[key], key, 'exec')
        # Apply only this narrow change to the shared files; unrelated recovery edits stay intact.
        path = d.ROOT / 'Labs/MimicKitTraining' / name
        local = path.read_text()
        if new not in local:
            assert local.count(old) == 1, name
            path.write_text(local.replace(old, new))
    cfg = yaml.safe_load(entries['prepared/env_config.yaml'])
    cfg['perturbed_motion']['pushed_idle_failure_penalty'] = 100.
    entries['prepared/env_config.yaml'] = yaml.safe_dump(cfg, sort_keys=False).encode()

    # Execute the exact added reward block against FAIL, timeout, success, and unrelated rows.
    tree = ast.parse(entries['pipeline/perturbed_omni.py'])
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_update_done')
    index = next(i for i,n in enumerate(method.body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'idle_penalty' for t in n.targets))
    block = ast.Module(body=method.body[index:index+2], type_ignores=[])
    e = SimpleNamespace(_perturb_cfg=cfg['perturbed_motion'],
        _final=SimpleNamespace(minus=torch.tensor([True, True, True, True, False, False])),
        _done_buf=torch.tensor([1, 3, 2, 0, 1, 3]), _reward_buf=torch.full((6,), .25))
    flags = SimpleNamespace(FAIL=SimpleNamespace(value=1))
    exec(compile(block, '<production-reward-block>', 'exec'), dict(self=e, DoneFlags=flags))
    torch.testing.assert_close(e._reward_buf, torch.tensor([-99.75,.25,.25,.25,.25,.25]))

    # Replay validation must accept the actual terminal cost and reject a missing one.
    from replay import convert_arrays
    from test_replay_failure_penalty import ReplayPenaltyTest
    case = ReplayPenaltyTest()
    for flag in (1, 3, 2):
        args = list(case.recording(flag))
        args[0].pop('loco_failure_penalty')
        args[0]['pushed_idle_failure_penalty'] = 100.
        convert_arrays(*args)
    args = list(case.recording(1))
    args[0].pop('loco_failure_penalty')
    args[0]['pushed_idle_failure_penalty'] = 100.
    args[2][-1,2] += 100
    try: convert_arrays(*args)
    except AssertionError: pass
    else: raise AssertionError('Missing penalty was not rejected')

    source = OUT / 'source-stored.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_STORED) as z:
        for n,data in entries.items(): z.writestr(n,data)
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    key = 'mimickit/pipeline_20261014/pushed-idle-penalty/source_' + sha[:12] + '.zip'
    plan.update(source=dict(local=str(source),key=key,sha256=sha),
                run_suffix='uefn_locomotion_idle_failure100_1024')
    (OUT/'prepared.json').write_text(json.dumps(plan,indent=2))
    evidence = dict(only_changed=['pipeline/'+n for n in edits]+['prepared/env_config.yaml'],
                    reward_test=e._reward_buf.tolist(), replay_failure_timeout_success_pass=True,
                    missing_penalty_rejected=True, source_sha256=sha)
    (OUT/'verification.json').write_text(json.dumps(evidence,indent=2))
    print('Tests passed; uploading source',flush=True)
    c=d.cloud.s3(); c.put_object(Bucket=d.cloud.rp.VOLUME_ID,Key=key,Body=source.read_bytes())
    print('Source uploaded; verifying persistent readback',flush=True)
    d.verified_readback(c,d.cloud.rp.VOLUME_ID,key,sha)
    active=json.loads((d.OUT/'active_run.json').read_text())
    d.save('ae30-switch',dict(old_run=active['run'],pod=active['pod'],source=plan['source']))
    print(json.dumps(evidence),flush=True)

if __name__ == '__main__': prepare()
