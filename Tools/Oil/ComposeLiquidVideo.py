"""Two actual UE views at unchanged authored playback speed; bounded encoder work."""
from pathlib import Path
import subprocess,json,hashlib
root=Path(__file__).resolve().parents[2]/'Saved/Diagnostics/Oil/Bottle/Liquid'
test=json.loads((root/'test.json').read_text());assert all(test['checks'].values()),test['checks']
font='C\\:/Windows/Fonts/arial.ttf'
def label(text):return f"drawtext=fontfile='{font}':text='{text}':x=18:y=20:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=7"
filters=f"[0:v]{label('BOTTLE MOTION AND SETTLING')}[a];[1:v]{label('SAME OIL - HIGH VIEW')}[b];[a][b]hstack=inputs=2[v]"
dest=root/'oil-inside-preview.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-y','-i',str(root/'side.mp4'),'-i',str(root/'above.mp4'),
    '-filter_complex_threads','1','-filter_complex',filters,'-map','[v]','-t','8','-c:v','libx264','-preset','fast','-crf','20','-threads','1',
    '-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
subprocess.run(['ffmpeg','-v','error','-xerror','-threads','1','-i',str(dest),'-f','null','-'],check=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
(root/'receipt.json').write_text(json.dumps({'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'width':1280,'height':640,'fps':30,'seconds':8,'checks':test['checks'],'update_us':test['update_us']},indent=2))
print(dest)
