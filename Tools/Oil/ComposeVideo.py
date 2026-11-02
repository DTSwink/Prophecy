"""Show the real mesh-floor throw, then the same run's Landscape throw, at 1x."""
import json, shutil, subprocess, sys
from pathlib import Path

root=Path(__file__).resolve().parents[2]
union='--union' in sys.argv
full_splash=union or '--splash' in sys.argv
folder=root/'Saved/Diagnostics/Oil'/('Union/Video' if union else ('Splash/Video' if full_splash else ('Edge/Video' if '--edge' in sys.argv else 'Revision/Video')))
receipt=json.loads((folder/'recording.json').read_text())
assert receipt['reason']=='complete' and receipt['frames']==330 and receipt['encoder_exits']==[0,0],receipt
assert all(receipt['checks'].values()),receipt['checks']
if full_splash:assert receipt['sheet_seen'] and receipt['sheet_cleaned']
font="C\\:/Windows/Fonts/segoeui.ttf"
filters=(f"[0:v]drawbox=x=0:y=0:w=1280:h=48:color=0x121820@0.85:t=fill,drawtext=fontfile='{font}':text='OIL / mesh floor':x=24:y=13:fontsize=23:fontcolor=white[a];"
         f"[1:v]drawbox=x=0:y=0:w=1280:h=48:color=0x121820@0.85:t=fill,drawtext=fontfile='{font}':text='OIL / Landscape':x=24:y=13:fontsize=23:fontcolor=white[b];"
         f"[a][b]concat=n=2:v=1:a=0,drawtext=fontfile='{font}':text='1x speed   |   4s hold + 4s fade':x=925:y=17:fontsize=18:fontcolor=0xc9d5e5[v]")
final=folder/('oil-union.mp4' if union else ('oil-splash.mp4' if full_splash else ('oil-edge-fixed.mp4' if '--edge' in sys.argv else 'oil-revised.mp4')))
args=[shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-y','-i',str(folder/'mesh.mp4'),'-i',str(folder/'landscape.mp4'),
      '-filter_complex',filters,'-map','[v]','-an','-c:v','libx264','-crf','18','-preset','medium','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(final)]
subprocess.run(args,check=True)
subprocess.run([shutil.which('ffprobe'),'-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,nb_frames,avg_frame_rate','-of','json',str(final)],check=True)
print(final)
