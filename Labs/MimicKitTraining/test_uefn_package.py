"""CPU-only deployment/guard checks; no cloud calls or training workloads."""
import io,sys,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'Saved/MimicKitUEFN/dependencies'),
             str(ROOT/'Saved/MimicKitTransfer/no-armature-3913/source/MimicKit/mimickit'),
             str(ROOT/'Labs/MimicKitTransfer')]
import torch
from uefn_package import runtime_files,verify_package
from uefn_engine import build_uefn_engine
from omni_walk import OmniWalkEnv
from health import install_guard


def main():
    paths=runtime_files(ROOT)
    for stale in (None,'assets/MimicKitTransfer/contact_engine.py'):
        memory=io.BytesIO()
        with zipfile.ZipFile(memory,'w') as package:
            for entry,path in paths.items():package.writestr(entry,b'stale' if entry==stale else path.read_bytes())
        with zipfile.ZipFile(memory) as package:
            try:verify_package(package,ROOT)
            except AssertionError:assert stale
            else:assert stale is None
    cfg=dict(uefn_asset_directory=str(ROOT/'Labs/MimicKitUEFN'),uefn_zero_joint_armature=True)
    with patch('contact_engine.ContactTransferEngine',return_value='verified') as verified:
        assert OmniWalkEnv._build_engine(None,cfg,512,'cpu',False)=='verified'
        verified.assert_called_once_with(cfg,512,'cpu',False,False)
    with patch('uefn_engine.UefnNewtonEngine',return_value='historical'):
        assert build_uefn_engine(dict(cfg,uefn_jolt_contact_profile=False),1,'cpu',False)=='historical'
    events=[]
    def bad_solver():raise FloatingPointError('latched motor failure')
    fake=SimpleNamespace(_env=SimpleNamespace(_engine=SimpleNamespace(validate_transfer_solver=bad_solver)),
        _rollout_train=lambda steps:events.append('rollout'),
        _exp_buffer=SimpleNamespace(_buffers={'obs':torch.zeros(2,3,4)}))
    install_guard(fake,lambda detail:events.append(detail))
    try:fake._rollout_train(2)
    except FloatingPointError:pass
    else:raise AssertionError('Physics failure reached optimizer boundary')
    assert events[0]=='rollout' and events[1]['reason'].startswith('Physics solver rejected')
    fake._env._engine.validate_transfer_solver=lambda:None
    fake._rollout_train(2)
    fake._exp_buffer._buffers['obs'][0,0,0]=float('nan')
    try:fake._rollout_train(2)
    except FloatingPointError:pass
    else:raise AssertionError('Nonfinite rollout accepted')
    print('PASS: exact source inventory, stale rejection, default verified engine, explicit legacy control, solver/nonfinite PPO guards')


if __name__=='__main__':main()
