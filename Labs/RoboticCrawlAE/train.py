"""Isolated local crawl-only AE1 run. Refuses to overwrite an existing run."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import random
import shutil
import time
import traceback

import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter

from features import Autoencoder,Scorer,encode,SCHEMA
from prepare import prepare,ROOT,sha,atomic_json


def utc():return datetime.now(timezone.utc).isoformat()


def save_checkpoint(path,value):
    temporary=path.with_suffix('.tmp');torch.save(value,temporary);os.replace(temporary,path)


def evaluate(model,groups,mean,std):
    model.eval();result=[]
    with torch.no_grad():
        for x in groups:
            values=[]
            for batch in x.split(512):
                z=(batch-mean)/std;values.append(((model(z)-z)**2).mean(-1))
            result.append(torch.cat(values))
    return result


def score_diagnostics(model,data,mean,std,run,manifest):
    device=mean.device;model.eval()
    result={'schema':SCHEMA,'clips':[]}
    clean_groups=[torch.tensor(data[f'test_{i}'],device=device) for i in range(len(manifest['clips']))]
    clean_scores=evaluate(model,clean_groups,mean,std)
    all_results=[]
    with torch.no_grad():
        for i,clean in enumerate(clean_scores):
            raw=np.load(run/'data'/f'clip_{i}_30hz.npz');starts=data[f'test_starts_{i}']
            p=torch.tensor(np.stack([raw['position'][j:j+3] for j in starts]),device=device)
            r=torch.tensor(np.stack([raw['rotation'][j:j+3] for j in starts]),device=device)
            original=encode(p,r)
            checks={}
            # Temporal translation jitter keeps each individual pose rigid.
            jitter=p.clone();jitter[:,1,:,0]+=.08;jitter[:,2,:,0]-=.08
            # Localized 10cm body displacement checks sensitivity to pose defects.
            distorted=p.clone();distorted[:,2,4,2]+=.10
            # Shuffle a temporally distant held-out final pose into the window.
            swapped=p.clone();swapped_r=r.clone()
            swapped[:,2]=torch.roll(p[:,2],max(1,len(p)//2),0)
            swapped_r[:,2]=torch.roll(r[:,2],max(1,len(p)//2),0)
            candidates={'root_jitter_8cm':encode(jitter,r),'body_jump_10cm':encode(distorted,r),
                        'mismatched_last_pose':encode(swapped,swapped_r)}
            for name,x in candidates.items():
                score=evaluate(model,[x],mean,std)[0]
                checks[name]=dict(mean=float(score.mean()),median=float(score.median()),
                    fraction_above_matching_clean=float((score>clean).float().mean()),
                    median_error_increase=float((score-clean).median()))
            angle=1.73;c,s=np.cos(angle),np.sin(angle)
            yaw=torch.tensor([[c,-s,0],[s,c,0],[0,0,1]],device=device,dtype=p.dtype)
            rotated=encode((yaw@p.unsqueeze(-1)).squeeze(-1)+torch.tensor([4.,-3.,0.],device=device),yaw@r)
            score_yaw=evaluate(model,[rotated],mean,std)[0]
            score_error=float((score_yaw-clean).abs().max())
            assert torch.allclose(rotated,original,atol=3e-5,rtol=0)
            row=dict(label=manifest['clips'][i]['label'],test_windows=len(clean),clean_mean=float(clean.mean()),
                clean_median=float(clean.median()),clean_p95=float(torch.quantile(clean,.95)),
                global_yaw_score_max_absolute_error=score_error,corruptions=checks)
            result['clips'].append(row);all_results.append(clean)
        result['clean_test_p95']=float(torch.quantile(torch.cat(all_results),.95))
        result['basic_corruption_check_passed']=all(row['corruptions'][n]['fraction_above_matching_clean']>=.8 for row in result['clips'] for n in ('root_jitter_8cm','body_jump_10cm'))
        result['deployment_status']='candidate_for_crawling_agent_integration' if result['basic_corruption_check_passed'] else 'requires_score_review_before_integration'
        result['scope']='Short-term crawl/idle prior; held-out blocks from the same source motions. No controller training/integration in this AE run.'
    atomic_json(run/'score-validation.json',result)
    return result


def main(run,steps,reuse_data=None,patience=8,native_sources=None):
    run.mkdir(parents=True,exist_ok=False)
    started=time.time()
    atomic_json(run/'status.json',dict(state='preparing',pid=os.getpid(),started_utc=utc()))
    source=run/'source';source.mkdir()
    for file in Path(__file__).parent.glob('*.py'):shutil.copy2(file,source/file.name)
    config=dict(schema=SCHEMA,hidden_dim=512,hidden_layers_per_side=2,latent_dim=128,
        input_dim=405,batch_size=512,optimizer='AdamW',learning_rate=.001,weight_decay=.00001,
        steps=steps,seed=1234,input_noise_std=0.,loss='mean squared normalized reconstruction error',
        lr_schedule='1e-3 through 70%, 3e-4 through 90%, 1e-4 thereafter',
        checkpoint_selection='lowest equal-clip mean validation reconstruction error',
        early_stopping_patience_checks=patience,validation_interval=250,
        prepared_data_source=str(reuse_data) if reuse_data else None,
        local_only=True,only_user_crawls=True,locomotion_run_untouched=True)
    atomic_json(run/'config.json',config)
    if reuse_data:
        manifest=json.loads((reuse_data/'dataset.json').read_text(encoding='utf-8'))
        assert manifest['schema']==SCHEMA and (manifest.get('only_three_user_crawls') or manifest.get('only_user_crawl_collection'))
        assert sha(reuse_data/'features.npz')==manifest['features_sha256']
        assert json.loads((reuse_data/'preflight.json').read_text(encoding='utf-8'))['passed']
        shutil.copytree(reuse_data,run/'data')
        assert sha(run/'data/features.npz')==manifest['features_sha256']
    else:
        manifest=prepare(run/'data',native_sources=native_sources)
    print(json.dumps(dict(stage='data_ready',clips=[dict(label=c['label'],frames=c['frames_30hz'],splits=c['splits']) for c in manifest['clips']]),ensure_ascii=True),flush=True)
    assert torch.cuda.is_available(),'Expected local CUDA device; refusing an unannounced CPU fallback'
    device=torch.device('cuda');torch.set_num_threads(2);torch.set_float32_matmul_precision('high')
    random.seed(1234);np.random.seed(1234);torch.manual_seed(1234);torch.cuda.manual_seed_all(1234)
    data=np.load(run/'data/features.npz')
    mean=torch.tensor(data['mean'],device=device);std=torch.tensor(data['std'],device=device)
    clip_count=len(manifest['clips'])
    train=[torch.tensor(data[f'train_{i}'],device=device) for i in range(clip_count)]
    validation=[torch.tensor(data[f'validation_{i}'],device=device) for i in range(clip_count)]
    model=Autoencoder().to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.00001)
    writer=SummaryWriter(str(run/'tensorboard'));best=float('inf');best_step=0;stale_checks=0
    (run/'checkpoints').mkdir()
    config.update(device=torch.cuda.get_device_name(),parameter_count=sum(p.numel() for p in model.parameters()),
        dtype='float32 with high-precision matmul setting',dataset_sha256=sha(run/'data/dataset.json'))
    atomic_json(run/'config.json',config)
    print(json.dumps(dict(stage='training',pid=os.getpid(),device=config['device'],parameters=config['parameter_count'])),flush=True)
    for step in range(1,steps+1):
        lr=.001 if step<=steps*.7 else .0003 if step<=steps*.9 else .0001
        for group in optimizer.param_groups:group['lr']=lr
        counts=[512//clip_count+int((i-step)%clip_count<512%clip_count) for i in range(clip_count)]
        batch=torch.cat([x[torch.randint(len(x),(counts[i],),device=device)] for i,x in enumerate(train)])
        batch=(batch-mean)/std
        model.train();optimizer.zero_grad(set_to_none=True)
        loss=((model(batch)-batch)**2).mean()
        if not torch.isfinite(loss):raise ValueError('Non-finite training loss')
        loss.backward();optimizer.step()
        if step==1 or step%25==0:
            writer.add_scalar('loss/train',float(loss.detach()),step)
        if step==1 or step%250==0 or step==steps:
            val=evaluate(model,validation,mean,std);val_mean=float(torch.stack([v.mean() for v in val]).mean())
            if val_mean<best:best=val_mean;best_step=step;improved=True;stale_checks=0
            else:improved=False;stale_checks+=1
            state=dict(schema=SCHEMA,config=config,body_names=manifest['body_names'],step=step,
                model=model.state_dict(),optimizer=optimizer.state_dict(),mean=mean.cpu(),std=std.cpu(),
                best_validation=best,best_step=best_step,torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state(),
                dataset_sha256=config['dataset_sha256'])
            if improved:save_checkpoint(run/'checkpoints/best.pt',state)
            save_checkpoint(run/'checkpoints/latest.pt',state)
            elapsed=time.time()-started
            status=dict(state='training',pid=os.getpid(),step=step,total_steps=steps,elapsed_seconds=elapsed,
                train_loss=float(loss.detach()),validation_loss=val_mean,best_validation=best,best_step=best_step,
                per_clip_validation=[float(v.mean()) for v in val],device=config['device'],updated_utc=utc())
            atomic_json(run/'status.json',status)
            with (run/'metrics.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(status)+'\n')
            writer.add_scalar('loss/validation_balanced',val_mean,step)
            for i,v in enumerate(val):writer.add_scalar(f'validation/clip_{i}',float(v.mean()),step)
            writer.flush();print(json.dumps(status),flush=True)
            if patience and stale_checks>=patience:
                print(json.dumps(dict(stage='early_stopping',step=step,best_step=best_step,stale_checks=stale_checks)),flush=True)
                break
    best_state=torch.load(run/'checkpoints/best.pt',map_location=device,weights_only=False)
    model.load_state_dict(best_state['model']);model.eval().requires_grad_(False)
    result=score_diagnostics(model,data,mean,std,run,manifest)
    scorer=Scorer(model.cpu(),mean.cpu(),std.cpu()).eval()
    torch.jit.script(scorer).save(str(run/'scorer.pt'))
    # Check exported scoring and gradients; runtime can use the shared encoder.
    test=torch.tensor(data['test_0'][:4],requires_grad=True)
    loaded=torch.jit.load(str(run/'scorer.pt'));score=loaded(test)
    np.testing.assert_allclose(score.detach().numpy(),scorer(test).detach().numpy(),atol=1e-7)
    score.sum().backward();assert torch.isfinite(test.grad).all()
    completed=dict(state='complete',pid=os.getpid(),steps=step,max_steps=steps,
        early_stopped=step<steps,best_step=best_step,best_validation=best,
        elapsed_seconds=time.time()-started,completed_utc=utc(),scorer=str(run/'scorer.pt'),
        scorer_sha256=sha(run/'scorer.pt'),score_validation=result['deployment_status'],clip_count=clip_count,
        locomotive_training_modified=False)
    atomic_json(run/'completed.json',completed);atomic_json(run/'status.json',completed);writer.close()
    print(json.dumps(completed),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);parser.add_argument('--steps',type=int,default=12000)
    parser.add_argument('--reuse-data',type=Path);parser.add_argument('--patience',type=int,default=8)
    parser.add_argument('--native-sources',type=Path)
    args=parser.parse_args()
    if args.run.exists():raise SystemExit('Refusing to overwrite an existing run')
    try:main(args.run.resolve(),args.steps,args.reuse_data.resolve() if args.reuse_data else None,args.patience,args.native_sources)
    except BaseException as error:
        if args.run.exists():atomic_json(args.run/'status.json',dict(state='failed',pid=os.getpid(),error=str(error),traceback=traceback.format_exc(),updated_utc=utc()))
        raise
