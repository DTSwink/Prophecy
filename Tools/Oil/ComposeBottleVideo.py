"""Assemble actual captured bottle / mesh-floor / landscape views, without changing playback speed."""
from pathlib import Path
import subprocess,json,struct,zlib
root=Path(__file__).resolve().parents[2]/'Saved/Diagnostics/Oil/Bottle'
video=root/'Video';receipt=json.loads((video/'recording.json').read_text())
assert receipt['reason']=='complete' and all(receipt['checks'].values())
# UE's export writer can leave a stale tail after IEND on a shorter overwrite.
# Retain the validated PNG unchanged and remove only non-image trailing bytes.
hero=video/'bottle-close.png';data=hero.read_bytes();offset=8
assert data[:8]==b'\x89PNG\r\n\x1a\n'
while offset+12<=len(data):
    size=struct.unpack_from('>I',data,offset)[0];end=offset+size+12
    assert end<=len(data) and zlib.crc32(data[offset+4:end-4])==struct.unpack_from('>I',data,end-4)[0]
    kind=data[offset+4:offset+8];offset=end
    if kind==b'IEND':break
assert kind==b'IEND';hero.write_bytes(data[:offset])
font='C\\:/Windows/Fonts/arial.ttf'
def label(text):return f"drawtext=fontfile='{font}':text='{text}':x=25:y=25:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=10"
filters=f"[0:v]fps=30,format=yuv420p,{label('FAB BOTTLE - 20 PREPARED PIECES')}[a];[1:v]{label('MESH FLOOR - SHATTER, FADE AND OIL PHYSICS')}[b];[2:v]{label('LANDSCAPE')}[c];[a][b][c]concat=n=3:v=1:a=0[v]"
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-y','-loop','1','-framerate','30','-t','2','-i',str(video/'bottle-close.png'),
    '-i',str(video/'mesh.mp4'),'-i',str(video/'landscape.mp4'),'-filter_complex',filters,'-map','[v]',
    '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(root/'oil-bottle-preview.mp4')],check=True,timeout=90)
print(root/'oil-bottle-preview.mp4')
