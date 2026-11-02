"""Splash/landing, synchronized wet/dry cube comparison, then Landscape."""
import json,shutil,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
folder=root/('Saved/Diagnostics/Oil/Airborne/Video' if '--airborne' in sys.argv else 'Saved/Diagnostics/Oil/Landing/Video')
r=json.loads((folder/'recording.json').read_text())
assert r['reason']=='complete' and r['frames']==330 and r['encoder_exits']==[0,0,0]
assert all(r['checks'].values()) and r['sheet_seen'] and r['sheet_cleaned'],r['checks']
font="C\\:/Windows/Fonts/segoeui.ttf"
def label(text,x=24,y=17,size=22):return f"drawtext=fontfile='{font}':text='{text}':x={x}:y={y}:fontsize={size}:fontcolor=white"
title="drawbox=x=0:y=0:w=1280:h=50:color=0x121820@0.85:t=fill,"
wet=round(r['travel_cm']['wet']);dry=round(r['travel_cm']['dry'])
f=("[0:v]split=3[m0][m1][m2];"
   "[m0]trim=end=3,setpts=PTS-STARTPTS,"+title+label('OIL / sheet lands into a connected puddle')+"[a];"
   "[m1]trim=start=3:end=7,setpts=PTS-STARTPTS,crop=960:720:320:0,scale=640:480,pad=640:720:0:120:color=0x121820,"+label('OILED',24,55)+"[wet];"
   "[2:v]trim=start=3:end=7,setpts=PTS-STARTPTS,crop=960:720:320:0,scale=640:480,pad=640:720:0:120:color=0x121820,"+label('DRY / same cube and initial speed',24,55)+"[dry];"
   "[wet][dry]hstack,"+label('Both receive one push at 150 cm/s - then native physics only',24,635,22)+","+
   label(f'Distance after 2.5 seconds - oil {wet} cm / dry {dry} cm',24,675,20)+"[b];"
   "[m2]trim=start=7,setpts=PTS-STARTPTS,"+title+label('OIL / shared visual and friction fade')+"[c];"
   "[1:v]setpts=PTS-STARTPTS,"+title+label('OIL / Landscape - same surface landing checks')+"[d];"
   "[a][b][c][d]concat=n=4:v=1:a=0[v]")
final=folder/'oil-sheet-landing-and-physics.mp4'
subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-y','-i',str(folder/'mesh.mp4'),'-i',str(folder/'landscape.mp4'),'-i',str(folder/'dry.mp4'),
    '-filter_complex',f,'-map','[v]','-an','-c:v','libx264','-crf','18','-preset','medium','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(final)],check=True)
info=subprocess.check_output([shutil.which('ffprobe'),'-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,nb_frames,avg_frame_rate','-of','json',str(final)])
(folder/'video.json').write_bytes(info);print(info.decode());print(final)
