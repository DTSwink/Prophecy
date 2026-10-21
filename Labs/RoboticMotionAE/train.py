"""Train the restored AE1 architecture on prepared physical motion windows."""
import json, os, shutil, sys, time
from pathlib import Path
import numpy as np
import torch
from torch.utils.tensorboard import SummaryWriter
from features import Autoencoder, Scorer, encode, SCHEMA
from prepare import OUT, ROOT, sha, atomic_json
OUT=ROOT/'Saved/RoboticMotionAE/20261019_mse_fullbody'


def score(model,x,mean,std):
    values=[]
    with torch.no_grad():
        for batch in x.split(512):
            z=(batch-mean)/std;values.append((model(z)-z).square().mean(-1))
    return torch.cat(values)


def diagnostics(model,data,manifest,mean,std,run):
    rows=[];all_clean=[];max_yaw_feature=0.;max_yaw_score=0.
    device=mean.device
    with torch.no_grad():
        for i,clip in enumerate(manifest['clips']):
            starts=data[f'test_starts_{i}']
            # Up to 256 evenly spaced held-out windows per motion for corruption checks.
            starts=starts[np.unique(np.linspace(0,len(starts)-1,min(len(starts),256),dtype=int))]
            with np.load(OUT/'data'/f'clip_{i}_30hz.npz') as raw:
                ix=starts[:,None]+np.arange(3)[None,:]
                p=torch.tensor(raw['position'][ix],device=device);r=torch.tensor(raw['rotation'][ix],device=device)
            # Remove a common world translation before numerical yaw testing.
            p=p-p[:,:1,:1,:]*torch.tensor([1.,1.,0.],device=device)
            x=encode(p,r);clean=score(model,x,mean,std);all_clean.append(clean.cpu())
            jitter=p.clone();jitter[:,1,:,0]+=.08;jitter[:,2,:,0]-=.08
            distorted=p.clone();distorted[:,2,4,2]+=.10
            swapped=p.clone();swapped_r=r.clone();shift=max(1,len(p)//2)
            swapped[:,2]=torch.roll(p[:,2],shift,0);swapped_r[:,2]=torch.roll(r[:,2],shift,0)
            tests={}
            for name,changed in [('root_jitter_8cm',encode(jitter,r)),('body_jump_10cm',encode(distorted,r)),
                                 ('mismatched_last_pose',encode(swapped,swapped_r))]:
                if name=='mismatched_last_pose' and len(clean)<2:
                    tests[name]=dict(tested=False,fraction_above_clean=None,reason='Only one held-out window')
                    continue
                noisy=score(model,changed,mean,std)
                tests[name]=dict(mean=float(noisy.mean()),fraction_above_clean=float((noisy>clean).float().mean()),
                                 median_increase=float((noisy-clean).median()))
            c,s=np.cos(1.73),np.sin(1.73)
            yaw=torch.tensor([[c,-s,0],[s,c,0],[0,0,1]],device=device,dtype=p.dtype)
            rotated=encode((yaw@p.unsqueeze(-1)).squeeze(-1)+torch.tensor([4.,-3.,0.],device=device),yaw@r)
            ferr=float((rotated-x).abs().max());assert ferr<3e-5,(i,ferr)
            serr=float((score(model,rotated,mean,std)-clean).abs().max())
            max_yaw_feature=max(max_yaw_feature,ferr);max_yaw_score=max(max_yaw_score,serr)
            rows.append(dict(id=i,label=clip['label'],windows=len(clean),clean_mean=float(clean.mean()),
                clean_p95=float(torch.quantile(clean,.95)),corruptions=tests))
    clean=torch.cat(all_clean)
    result=dict(clips=rows,clean_sample_p50=float(clean.median()),clean_sample_p95=float(torch.quantile(clean,.95)),
        heading_translation_max_feature_error=max_yaw_feature,heading_translation_max_score_error=max_yaw_score,
        scope='Short-horizon motion prior, within-motion test blocks; no independent-subject generalization claim',
        corruption_fraction_by_clip={name:float(np.mean([r['corruptions'][name]['fraction_above_clean'] for r in rows if r['corruptions'][name]['fraction_above_clean'] is not None]))
            for name in ('root_jitter_8cm','body_jump_10cm','mismatched_last_pose')})
    atomic_json(run/'validation.json',result);return result


def main(run_dir=None, hidden_dim=1024, hidden_layers=3):
    run=run_dir or OUT/'run';run.mkdir(exist_ok=False)
    source=run/'source';source.mkdir()
    for p in Path(__file__).parent.glob('*.py'):shutil.copy2(p,source/p.name)
    manifest=json.loads((OUT/'data/dataset.json').read_text())
    assert sha(OUT/'data/features.npz')==manifest['features_sha256']
    assert json.loads((OUT/'data/preflight.json').read_text())['passed']
    torch.set_num_threads(2);torch.set_float32_matmul_precision('high');torch.manual_seed(1234);np.random.seed(1234)
    assert torch.cuda.is_available();device=torch.device('cuda')
    data=np.load(OUT/'data/features.npz');mean=torch.tensor(data['mean'],device=device);std=torch.tensor(data['std'],device=device)
    n=len(manifest['clips']);groups={};row_weights={}
    for split in ('train','validation','test'):
        groups[split]=torch.tensor(np.concatenate([data[f'{split}_{i}'] for i in range(n)]),device=device)
        if 'clip_weights' in data:
            w=np.concatenate([np.full(len(data[f'{split}_{i}']),data['clip_weights'][i]/len(data[f'{split}_{i}'])) for i in range(n)])
        else:w=np.ones(len(groups[split]))
        row_weights[split]=torch.tensor(w/w.sum(),dtype=torch.float32,device=device)
    cumulative=torch.cumsum(row_weights['train'],0);cumulative[-1]=1.
    train=(groups['train']-mean)/std
    model=Autoencoder(hidden_dim,hidden_layers).to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=1e-5)
    steps=12000;best=float('inf');best_step=0;started=time.time()
    config=dict(schema=SCHEMA,hidden_dim=hidden_dim,hidden_layers_per_side=hidden_layers,latent_dim=128,input_dim=405,
        parameters=sum(p.numel() for p in model.parameters()),batch_size=512,steps=steps,optimizer='AdamW',lr=.001,weight_decay=1e-5,
        seed=1234,noise_std=0.,device=torch.cuda.get_device_name(),clip_count=n,
        windows={s:len(x) for s,x in groups.items()},sampling=manifest['sampling'],split=manifest['split'],
        initialization='Fresh random model and AdamW; no checkpoint loaded',
        checkpoint_selection='lowest sampling-weighted validation normalized reconstruction MSE',features_sha256=manifest['features_sha256'])
    atomic_json(run/'config.json',config);writer=SummaryWriter(str(run/'tensorboard'))
    print(json.dumps(config),flush=True)
    for step in range(1,steps+1):
        lr=.001 if step<=8400 else .0003 if step<=10800 else .0001
        for group in optimizer.param_groups:group['lr']=lr
        batch=train[torch.searchsorted(cumulative,torch.rand(512,device=device))]
        model.train();optimizer.zero_grad(set_to_none=True);loss=(model(batch)-batch).square().mean()
        assert torch.isfinite(loss);loss.backward();optimizer.step()
        if step%25==0:writer.add_scalar('loss/train',float(loss.detach()),step)
        if step==1 or step%250==0:
            model.eval();val=float((score(model,groups['validation'],mean,std)*row_weights['validation']).sum())
            if val<best:
                best=val;best_step=step
                state=dict(model=model.state_dict(),mean=mean.cpu(),std=std.cpu(),step=step,config=config,body_names=manifest['body_names'])
                torch.save(state,run/'best.pt')
            status=dict(state='training',step=step,max_steps=steps,train_loss=float(loss.detach()),validation_loss=val,
                best_validation=best,best_step=best_step,elapsed_seconds=time.time()-started,pid=os.getpid())
            atomic_json(run/'status.json',status)
            with (run/'metrics.jsonl').open('a') as f:f.write(json.dumps(status)+'\n')
            writer.add_scalar('loss/validation',val,step);writer.add_scalar('lr',lr,step);writer.flush();print(json.dumps(status),flush=True)
    state=torch.load(run/'best.pt',map_location=device,weights_only=False);model.load_state_dict(state['model']);model.eval().requires_grad_(False)
    test=float((score(model,groups['test'],mean,std)*row_weights['test']).sum())
    train_mse=float((score(model,groups['train'],mean,std)*row_weights['train']).sum())
    validation=diagnostics(model,data,manifest,mean,std,run)
    scorer=Scorer(model.cpu(),mean.cpu(),std.cpu()).eval().requires_grad_(False)
    torch.jit.script(scorer).save(str(run/'motion_scorer.pt'))
    torch.jit.script(model).save(str(run/'autoencoder.pt'))
    loaded=torch.jit.load(str(run/'motion_scorer.pt'));probe=torch.tensor(data['test_0'][:8],requires_grad=True)
    np.testing.assert_allclose(loaded(probe).detach(),scorer(probe).detach(),atol=1e-7)
    loaded(probe).sum().backward();assert torch.isfinite(probe.grad).all() and probe.grad.abs().sum()>0
    result=dict(state='complete',steps=steps,best_step=best_step,best_validation=best,test_mse=test,train_mse_at_best=train_mse,
        elapsed_seconds=time.time()-started,clip_count=n,parameters=config['parameters'],scorer_sha256=sha(run/'motion_scorer.pt'),
        portable_export_parity_passed=True,finite_input_gradient=True,validation_summary={k:v for k,v in validation.items() if k!='clips'})
    atomic_json(run/'completed.json',result);atomic_json(run/'status.json',result);writer.close();print(json.dumps(result),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--data-root',type=Path,default=OUT)
    parser.add_argument('--run-dir',type=Path)
    parser.add_argument('--hidden-dim',type=int,default=1024)
    parser.add_argument('--hidden-layers',type=int,default=3)
    args=parser.parse_args();OUT=args.data_root.resolve()
    assert args.hidden_dim>0 and args.hidden_layers>0
    main(args.run_dir.resolve() if args.run_dir else None,args.hidden_dim,args.hidden_layers)
