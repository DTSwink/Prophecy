"""Exercise inherited resume/save behavior without allocating a GPU environment."""
import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch
import torch
from train import RecoveryRunner, MjlabOnPolicyRunner


def main():
    cfg={'rig_sha256':'fixture','controller':{},'num_envs':1024}
    header={'iter':50,'infos':{'physical_recovery':cfg,'training_transitions':1224*1024,
                              'env_state':{'common_step_counter':1224}}}
    def inherited_load(runner,*a,**k):
        runner.current_learning_iteration=header['iter']
        runner.env.common_step_counter=header['infos']['env_state']['common_step_counter']
    saved=[]
    def inherited_save(runner,path,infos):saved.append(infos)
    with TemporaryDirectory() as temp,patch.object(torch,'load',return_value=header),\
         patch.object(MjlabOnPolicyRunner,'load',inherited_load),patch.object(MjlabOnPolicyRunner,'save',inherited_save):
        runner=object.__new__(RecoveryRunner)
        runner.env=SimpleNamespace(cfg=cfg,num_envs=512,common_step_counter=0,history_count=1,
            episode_length_buf=torch.tensor([1]),max_episode_length=240,history=torch.zeros(240,1,95),initial='fixed')
        runner.cfg={'num_steps_per_env':24};runner.logger=SimpleNamespace(tot_timesteps=0)
        runner.load('fixture.pt')
        assert runner.current_learning_iteration==51 and runner.step_offset==1224
        runner.env.common_step_counter+=24
        runner.save(str(Path(temp)/'model_51.pt'))
        assert saved[-1]['training_transitions']==1224*1024+24*512
        assert saved[-1]['transition_counter_version']==2
        # An ambiguous old resumed count must not silently become trusted.
        header['infos']['training_transitions']+=1024
        try:runner.load('fixture.pt')
        except ValueError as e:assert 'ambiguous' in str(e)
        else:raise AssertionError('Legacy double count accepted')
        runner.load('fixture.pt',training_transitions=1224*1024)
        assert runner.transition_offset==1224*1024
    # Match upstream's dimensional sum, which scales alongside entropy.
    changes=torch.full((3,54),2.)
    assert torch.equal(changes.square().sum(-1),torch.full((3,),216.))
    assert torch.allclose(changes.square().sum(-1)/changes.square().mean(-1),torch.full((3,),54.))
    report={'passed':True,'resume_restores_inherited_counter':True,'changed_batch_counts_once':True,
            'ambiguous_legacy_count_rejected':True,'action_rate_sum_to_mean_ratio':54}
    from recovery_env import OUT
    (OUT/'training-accounting-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':main()
