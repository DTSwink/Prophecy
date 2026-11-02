"""Three real cameras, each at normal speed followed by a labelled slow replay."""
import json, shutil, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
folder=root/'Saved/Diagnostics/Oil/Airborne/Angles'
if '--niagara-flower' in sys.argv:folder=root/'Saved/Diagnostics/Oil/NiagaraFlower/Angles'
r=json.loads((folder/'recording.json').read_text())
assert r['reason']=='complete' and r['frames']==180 and r['fps']==60
assert r['encoder_exits']==[0,0,0] and all(r['checks'].values())
font="C\\:/Windows/Fonts/segoeui.ttf"
names=[('overhead','OVERHEAD'),('low','NEAR FLOOR / camera 22 cm high'),('angled','ANGLED')]
filters=[];sequence=[]
for i,(_,title) in enumerate(names):
    filters.append(f'[{i}:v]split=2[normal{i}][slow{i}]')
    for key,trim,timing,label in [('normal','trim=end=3','PTS-STARTPTS','normal speed'),('slow','trim=start=0.4:end=1.4','3*(PTS-STARTPTS)','1/3 speed replay')]:
        tag=f'{key}out{i}';sequence.append(f'[{tag}]')
        filters.append(f"[{key}{i}]{trim},setpts={timing},fps=60,drawbox=x=0:y=0:w=1280:h=50:color=0x121820@0.85:t=fill,drawtext=fontfile='{font}':text='{title} / {label}':x=24:y=15:fontsize=23:fontcolor=white[{tag}]")
filters.append(''.join(sequence)+'concat=n=6:v=1:a=0[v]')
final=folder/'oil-splash-three-angles.mp4'
args=[shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-y']
for name,_ in names:args+=['-i',str(folder/(name+'.mp4'))]
args+=['-filter_complex',';'.join(filters),'-map','[v]','-an','-c:v','libx264','-crf','18','-preset','medium','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(final)]
subprocess.run(args,check=True)
info=subprocess.check_output([shutil.which('ffprobe'),'-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,nb_frames,avg_frame_rate','-of','json',str(final)])
(folder/'video.json').write_bytes(info);print(info.decode());print(final)
