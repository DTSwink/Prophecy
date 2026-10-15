"""CPU checks for display rewind, fixed-tick stepping, and cube coordinates."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,'C:/Users/singerie/Documents/Cursor/stepper/training')
from physical_checkpoint_viewer import FrameHistory, seek, launch_cube, world_pose, tick


def main():
    history=FrameHistory(3)
    def frame(t):return {'tick':t,'positions':[[t,1,0]],'rotations':[np.eye(3).tolist()],
                        'centers':[[t+.2,1,0]],'axes':[np.eye(3).tolist()],'shapes':[],'status':'test'}
    for t in range(5):history.append(frame(t))
    assert history.first==2 and history.last==4 and len(history.frames)==3
    assert history.sample(-1)['tick']==2 and history.sample(3)['tick']==3
    commands=[];status=[]
    client=SimpleNamespace(history=history,latest=history.sample(4),ready=True,pending=False,manual_advance=False,
        send=commands.append,accumulator=0.,poll=lambda:False)
    actor=SimpleNamespace(kind='physical',physical=client,visible=True,offset=np.array([2.,0,3]),initial_root_yaw=1.)
    yaw=np.array([[0.,0,1],[0,1,0],[-1,0,0]])
    app=SimpleNamespace(actors=[actor],frame=4.,playing=False,camera_transition=None,status_var=SimpleNamespace(set=status.append),
        selected_actor=lambda:actor,actor_root_yaw_affects_velocity=lambda a:False,actor_root_yaw_matrix=lambda a:yaw,
        camera_render_view=lambda:(np.array([6.,2,5]),None,None),update_timeline=lambda:None,draw=lambda:None,
        speed_var=SimpleNamespace(get=lambda:1),update_follow_camera_target=lambda:None)
    seek(app,3);assert app.frame==3 and not commands
    launch_cube(app);assert not commands and 'live simulation' in status[-1]
    seek(app,4);launch_cube(app);assert commands[-1]['op']=='launch'
    # A cube origin must invert the exact display transform, including yaw.
    world,_=world_pose(app,actor,np.array([commands[-1]['origin']]),np.eye(3)[None],client.latest)
    np.testing.assert_allclose(world[0],app.camera_render_view()[0],atol=1e-6)
    commands.clear();seek(app,5,advance=True);assert commands==[{'op':'step'}] and client.manual_advance
    commands.clear();app.frame=2.;app.playing=True;tick(app,1/30)
    assert app.frame==3 and not commands # Playing recorded history does not rerun physics.
    history.append(frame(0));assert history.first==history.last==0 and len(history.frames)==1
    report={'passed':True,'bounded_history':True,'rewind_does_not_resimulate':True,'step_requests_one_policy_tick':True,
            'reset_clears_old_history':True,'cube_origin_inverts_display_yaw':True}
    out=Path(__file__).resolve().parents[2]/'Saved/Robotics/viewer-history-tests.json'
    out.write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':main()
