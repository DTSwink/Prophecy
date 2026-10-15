"""Exercise the owned viewer's public playback callbacks and OpenGL draw path.

This is an application integration test, not a screenshot/motion assessment.
No saved settings are changed, and the owned app/worker close on completion.
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path
sys.path.insert(0,'C:/Users/singerie/Documents/Cursor/stepper/training')
from model_viewer_app import ModelViewerApp


def main():
    p=argparse.ArgumentParser();p.add_argument('checkpoint',type=Path);args=p.parse_args()
    app=ModelViewerApp(checkpoint_path=args.checkpoint.resolve())
    errors=[];stage=0;deadline=time.monotonic()+90;step_tick=0
    def fail(exc):
        errors.append(str(exc));app.destroy()
    app.report_callback_exception=lambda typ,value,tb:fail(''.join(traceback.format_exception(typ,value,tb)))
    def check():
        nonlocal stage,step_tick
        try:
            if time.monotonic()>deadline:raise TimeoutError(f'Viewer stage {stage} timed out')
            actor=next((a for a in app.actors if a.kind=='physical'),None)
            if actor is not None and actor.physical.error:raise RuntimeError(actor.physical.error)
            if actor is not None and actor.physical.ready and not actor.physical.pending:
                client=actor.physical
                if stage==0:
                    assert len(client.latest['shapes'])==23
                    app.playing=True;stage=1
                elif stage==1 and client.history.last>=30:
                    app.playing=False;step_tick=client.history.last
                    app.step_frame(-1);assert int(app.frame)==step_tick-1
                    app.draw();app.step_frame(1);assert int(app.frame)==step_tick
                    app.step_frame(1);stage=2
                elif stage==2 and client.history.last>step_tick:
                    assert int(app.frame)==client.history.last
                    app.on_space_play(None);stage=3
                elif stage==3 and len(client.latest['shapes'])==24:
                    app.draw();app.stop_playback();stage=4
                elif stage==4 and client.latest['tick']==0:
                    assert len(client.latest['shapes'])==23 and len(client.history.frames)==1
                    app.draw();stage=5;app.destroy();return
            app.after(20,check)
        except Exception:fail(traceback.format_exc())
    app.after(200,check)
    try:app.mainloop()
    finally:
        for actor in getattr(app,'actors',[]):
            if actor.kind=='physical':actor.physical.close()
    report={'passed':stage==5 and not errors,'stage':stage,'errors':errors,
            'scope':'Actual Tk/OpenGL application callbacks; no visual screenshot or motion-quality certification'}
    out=Path(__file__).resolve().parents[2]/'Saved/Robotics/viewer-app-tests.json'
    out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    if not report['passed']:raise RuntimeError('Viewer integration failed; see receipt')


if __name__=='__main__':main()
