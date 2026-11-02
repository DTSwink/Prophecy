"""Actual impact capture, followed by an explicitly labelled slow replay."""
import json,hashlib,subprocess,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[2]/'Saved/Diagnostics/Oil/Bottle/Studio'
test=json.loads((root/'test.json').read_text());assert all(test['checks'].values()),test
start=max(0,(test['break_tick']-15)/60);end=(test['break_tick']+45)/60
font='C\\:/Windows/Fonts/arial.ttf'
def label(text):return f"drawtext=fontfile='{font}':text='{text}':x=20:y=22:fontsize=23:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=8"
f=f"[0:v]split[main][r];[main]{label('STUDIO LIGHTING - REAL JOLT IMPACT')}[a];[r]trim=start={start}:end={end},setpts=(PTS-STARTPTS)/0.4,fps=30,{label('IMPACT REPLAY - 0.4x SPEED')}[b];[a][b]concat=n=2:v=1:a=0[v]"
dest=root/'golden-oil-1080p.mp4'
flags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-y','-i',str(root/'studio-bottle-break.mp4'),'-filter_complex_threads','1','-filter_complex',f,'-map','[v]',
    '-c:v','libx264','-preset','fast','-crf','16','-threads','1','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True,timeout=90,creationflags=flags)
subprocess.run(['ffmpeg','-hide_banner','-v','error','-xerror','-threads','1','-i',str(dest),'-f','null','-'],check=True,timeout=60,creationflags=flags)
timings=sorted(test['liquid_update_us'])
(root/'receipt.json').write_text(json.dumps({'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'checks':test['checks'],'break_tick':test['break_tick'],'replay_speed':.4,'replay_range_seconds':[start,end],
 'resolution':test.get('capture_resolution'),
 'liquid_update_cpu_us':{'samples':len(timings),'median':statistics.median(timings),'p95':timings[int(.95*(len(timings)-1))],'max':max(timings)},'max_volume_error_fraction':test['max_volume_error'],
 'limits':'One moving bottle on this laptop; CPU mesh update/enqueue only, not GPU or many-bottle benchmark. Refraction is screen-space, not ray traced.'},indent=2))
print(dest)
