"""Compare only matched sample counts from existing training telemetry; no extra rollouts."""
import json
from pathlib import Path
import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


def compare(manifest, run_root):
    trials=[]
    for spec in manifest['trials']:
        directory=Path(run_root)/('mimickit_'+spec['name'])
        reader=EventAccumulator(str(directory),size_guidance={'scalars':0},purge_orphaned_data=False)
        reader.Reload()
        tags=reader.Tags()['scalars']
        events={tag:reader.Scalars(tag) for tag in tags}
        episodes={e.step:e.value for e in events.get('1_Info/Train_Episodes',[])}
        losses={e.step:-e.value for e in events.get('0_Main/Train_Return',[]) if episodes.get(e.step,0)>0 and np.isfinite(e.value)}
        trials.append((spec,directory,events,losses))
    common=min(max(losses,default=0) for _,_,_,losses in trials)
    window=50*128*32
    report=dict(common_samples=common,window_samples=window,trials=[])
    for spec,directory,events,losses in trials:
        matched=[v for step,v in losses.items() if common-window<step<=common]
        status=json.loads((directory/'status.json').read_text()) if (directory/'status.json').exists() else {}
        failure=json.loads((directory/'failure.json').read_text()) if (directory/'failure.json').exists() else None
        clip=[e.value for e in events.get('Misc/Clip_Frac',[]) if common-window<e.step<=common]
        report['trials'].append(dict(name=spec['name'],actor_lr=spec['actor_lr'],matched_window_mse=float(np.mean(matched)) if matched else None,
            matched_points=len(matched),latest_samples=status.get('samples'),latest_mse=-status.get('metrics',{}).get('mean_return',float('nan')),
            transitions_per_second=status.get('training_transitions_per_second'),failure=failure,
            matched_window_clip_fraction=float(np.mean(clip)) if clip else None))
    return report


if __name__=='__main__':
    out=Path('Saved/MimicKit')
    report=compare(json.loads((out/'sweep.json').read_text()),'C:/Users/singerie/Documents/Cursor/stepper/training/runs')
    (out/'sweep-comparison.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
