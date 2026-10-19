"""Readable local TensorBoard comparison; original event files remain untouched."""
import argparse
import json
import math
import time
from pathlib import Path
from runtime_deadline import RuntimeDeadline
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
from tensorboard.summary.writer.event_file_writer import EventFileWriter
from tensorboard.compat.proto.event_pb2 import Event
from tensorboard.compat.proto.summary_pb2 import Summary


def scalars(path):
    reader=EventAccumulator(str(path),size_guidance={'scalars':0},purge_orphaned_data=False)
    reader.Reload()
    return {tag:reader.Scalars(tag) for tag in reader.Tags()['scalars']}


class Dashboard:
    def __init__(self,manifest):
        self.manifest=manifest
        self.writers={}
        self.seen={}
        for run in manifest['runs']:
            target=Path(manifest['output'])/run['name']
            target.mkdir(parents=True,exist_ok=True)
            self.seen[run['name']]={(tag,e.step) for tag,events in scalars(target).items() for e in events}
            self.writers[run['name']]=EventFileWriter(str(target))

    def update(self):
        count=0
        for run in self.manifest['runs']:
            mse=run['objective'] in ('neutral_pose_mse','continuous_neutral_pose_mse','best_neutral_pose_mse','world_pose_mse')
            mapping={'0_Main/Train_Return':('loss/train' if mse else 'reward/train',-1 if mse else 1),
                     '0_Main/Test_Return':('loss/test' if mse else 'reward/test',-1 if mse else 1),
                     '0_Main/Train_Episode_Length':('episode/train_seconds',1/30),
                     '0_Main/Test_Episode_Length':('episode/test_seconds',1/30),
                     'Misc/Actor_Loss':('optimizer/actor',1),
                     'Misc/Critic_Loss':('optimizer/critic',1),'health/numerical_failure':('health/numerical_failure',1),
                     'health/solver_roundoff_warnings':('health/solver_roundoff_warnings',1)}
            for tag in ('solver_convergence_warnings','solver_motor_residual_nm','solver_contact_limit_velocity_residual'):
                mapping['health/'+tag]=('health/'+tag,1)
            for tag in ('policy_kl','policy_kl_proposed','actor_steps_accepted','actor_steps_rejected','actor_full_rollback','actor_learning_rate'):
                mapping['Misc/'+'_'.join(x.capitalize() for x in tag.split('_'))]=('optimizer/'+tag,1)
            if run['objective']=='world_pose_mse':
                mapping.update({('loss/'+key):('loss/'+key,1) for key in ('position_mse','orientation_mse','body_pose_mse','head_height_band','pelvis_height_band','feet_lateral','termination_remaining','total')})
            if run['objective'] in ('absolute_walk_mse','uefn_omni_absolute_walk','uefn_crawl_idle_mse'):
                mapping.update({('loss/'+key):('loss/'+key,1) for key in ('position_mse','linear_velocity_mse','rotation_mse','angular_velocity_mse','flat_com_velocity','pelvis_velocity_extra','auto_phase','body_total','total')})
                mapping.update({'Misc/Auto_Phase_Mse':('auto_phase/mse',1),'Misc/Auto_Phase_Weighted':('auto_phase/weighted_loss',1)})
            composite=run['objective']=='timed_best_pose_tail'
            if composite:
                mapping.pop('0_Main/Train_Return');mapping.pop('0_Main/Test_Return')
                mapping.update({('loss/'+key):('loss/'+key,1) for key in ('early_pose','tail_mse','joint_velocity','total')})
                if run.get('velocity_includes_pelvis'):
                    mapping['loss/joint_velocity']=('loss/velocity',1)
            name=run['name']
            amp=run['objective'] in ('amp_spinkick','amp_standing')
            if amp:
                # AMP's environment return is zero: its imitation reward is
                # computed by the discriminator after rollout collection.
                mapping.pop('0_Main/Train_Return')
                mapping.pop('0_Main/Test_Return')
                mapping.update({'Misc/Disc_Reward_Mean':('reward/imitation',1),
                                'Misc/Disc_Loss':('loss/discriminator',1),
                                'Misc/Disc_Agent_Acc':('discriminator/agent_accuracy',1),
                                'Misc/Disc_Demo_Acc':('discriminator/reference_accuracy',1)})
            for source in run['sources']:
                if not Path(source).exists():continue
                data=scalars(source)
                episode_counts={e.step:e.value for e in data.get('1_Info/Train_Episodes',[])}
                for old,(tag,scale) in mapping.items():
                    for e in data.get(old,[]):
                        # The first 32-step batch cannot finish a 45-step episode.
                        # Upstream logs zero then; it is not a measured pose error.
                        if old in ('0_Main/Train_Return','0_Main/Train_Episode_Length') and episode_counts.get(e.step)==0:continue
                        key=(tag,e.step)
                        if key in self.seen[name]:continue
                        self.writers[name].add_event(Event(wall_time=e.wall_time,step=e.step,
                            summary=Summary(value=[Summary.Value(tag=tag,simple_value=e.value*scale)])))
                        self.seen[name].add(key);count+=1
                # Preserve the exact latest measured train return even if a
                # short/failed run ended before the next scalar-file write.
                status_path=Path(source)/'status.json'
                if status_path.exists() and not amp and not composite:
                    status=json.loads(status_path.read_text());metrics=status.get('metrics',{})
                    sample=status.get('samples');value=metrics.get('mean_return')
                    key=('loss/train' if mse else 'reward/train',sample)
                    if (sample is not None and value is not None and metrics.get('num_eps',0)>0
                            and math.isfinite(value) and key not in self.seen[name]):
                        self.writers[name].add_event(Event(wall_time=status['updated_unix'],step=sample,
                            summary=Summary(value=[Summary.Value(tag=key[0],simple_value=value*(-1 if mse else 1))])))
                        self.seen[name].add(key);count+=1
                # Derive interval throughput; upstream's cumulative-samples /
                # segment-time metric is incorrect after a resumed run.
                events=data.get('1_Info/Wall_Time',[])
                for previous,current in zip(events,events[1:]):
                    seconds=(current.value-previous.value)*3600
                    key=('performance/transitions_per_second',current.step)
                    if seconds<=0 or key in self.seen[name]:continue
                    self.writers[name].add_event(Event(wall_time=current.wall_time,step=current.step,
                        summary=Summary(value=[Summary.Value(tag=key[0],simple_value=(current.step-previous.step)/seconds)])))
                    self.seen[name].add(key);count+=1
                final=Path(source)/'finished.json'
                evaluation=Path(source)/'evaluation.json'
                if final.exists() and evaluation.exists() and not amp and not composite:
                    result=json.loads(evaluation.read_text());replay=result.get('replay',{})
                    samples=replay.get('samples')
                    key=('loss/test' if mse else 'reward/test',samples)
                    if samples is not None and key not in self.seen[name]:
                        self.writers[name].add_event(Event(wall_time=replay['generated_unix'],step=samples,
                            summary=Summary(value=[Summary.Value(tag=key[0],simple_value=result['mean_return']*(-1 if mse else 1))])))
                        self.seen[name].add(key);count+=1
            self.writers[name].flush()
        return count

    def close(self):
        for writer in self.writers.values():writer.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('manifest',type=Path)
    parser.add_argument('--until',type=float,default=0);args=parser.parse_args()
    dashboard=Dashboard(json.loads(args.manifest.read_text()))
    live=dashboard.manifest.get('runtime_control')
    deadline=RuntimeDeadline(live['path'],live['pod_id'],args.until-180,reserve=-180) if live else None
    try:
        while True:
            count=dashboard.update()
            if count:print(f'Published {count} comparison points',flush=True)
            until=deadline.read() if deadline else args.until
            if time.time()>=until:break
            time.sleep(min(15,max(0,until-time.time())))
    finally:dashboard.close()


if __name__=='__main__':main()
