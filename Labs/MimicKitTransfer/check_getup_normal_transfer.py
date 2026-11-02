"""Frozen normal recovery rows, using their recorded authored-clock targets."""
from getup_transfer import *


def run(label):
    policy=Policy('native');archive=np.load(OUT/'native/replay.npz');reports=[]
    for index in (0,1):
        row,recorded=replay('native',index)
        target=archive['reference_pose'+('' if index==0 else '_1')].copy()
        points=row['target_deviation']['points']
        ids=[names.index(p['body']) for p in points]
        offsets=np.array([p['offset'] for p in points]);radii=np.array([p['radius_m'] for p in points])
        phase=np.array(row['frame_phase'][0][:2]);sim=Jolt(recorded[0]);current=np.array(sim.initial['bodies'])
        history=[current];distances=[];actions=[];terminal=2
        try:
            for tick in range(1,len(recorded)):
                action,pred=policy(observation(current,row,phase));phase=pred[0]
                current=np.array(sim.request('step '+' '.join(map(str,action[0])))['bodies'])
                desired=target[tick].copy()
                desired[:,:2]+=current[0,:2]-desired[0,:2]
                actual=current[ids,:3]+R.from_quat(current[ids,3:7]).apply(offsets)
                goal=desired[ids,:3]+R.from_quat(desired[ids,3:7]).apply(offsets)
                distance=np.linalg.norm(actual-goal,axis=-1)
                history.append(current);actions.append(action[0]);distances.append(distance)
                if np.any(distance>radii):terminal=1;break
        finally:sim.close()
        report=dict(row=index,terminal=terminal,ticks=tick,authored_ticks=len(recorded)-1,
                    reference_start_seconds=row['recovery_start_seconds'],
                    maximum_target_distances_m=dict(zip([p['body'] for p in points],np.max(distances,axis=0).tolist())))
        reports.append(report)
        np.savez_compressed(OUT/f'normal-{label}-row{index}.npz',states=history,actions=actions,distances=distances)
        print(json.dumps(report),flush=True)
    (OUT/f'normal-{label}.json').write_text(json.dumps(reports,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--unreal',action='store_true');parser.add_argument('--label',default='native-profile');args=parser.parse_args()
    if args.unreal:
        from getup_unreal import Channel,UnrealJolt
        channel=Channel();UnrealJolt.channel=channel;Jolt=UnrealJolt
        try:run('unreal-'+args.label)
        finally:channel.request('quit');channel.process.wait(60)
        assert channel.process.returncode==0
    else:run(args.label)
