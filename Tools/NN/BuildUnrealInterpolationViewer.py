"""Create a sibling comparison viewer; never alter the original or motion data."""
import argparse
import hashlib
import json
from pathlib import Path

UNREAL_ROTATION = r'''
// Matches ProphecyAgent.cpp::BlendAuthoredRotation (Current mode).
// UE's Angle/WeightedAngle/Alpha intermediates are float, quaternions are double.
function quatUnrealInterpolate(a,b,t){
  a=quatNormalize(a);b=quatNormalize(b);
  const f=Math.fround;
  let cosine=f(a.reduce((s,v,i)=>s+v*b[i],0));
  if(cosine<0){b=b.map(v=>-v);cosine=-cosine;}
  cosine=Math.max(0,Math.min(1,cosine));
  const angle=f(2*f(Math.acos(cosine)));
  if(angle<=1e-6)return a;
  const alpha=f(t);
  const weighted=f(Math.atan2(f(alpha*f(Math.sin(angle))),
    f(f(1-alpha)+f(alpha*f(Math.cos(angle))))));
  const amount=f(weighted/angle);
  // UE FQuat::Slerp uses the 0.9999 threshold, followed by normalization.
  let dot=a.reduce((s,v,i)=>s+v*b[i],0),sign=dot<0?-1:1;
  dot=Math.abs(dot);
  let wa=1-amount,wb=amount;
  if(dot<0.9999){
    const theta=Math.acos(dot),inverseSin=1/Math.sin(theta);
    wa=Math.sin((1-amount)*theta)*inverseSin;
    wb=Math.sin(amount*theta)*inverseSin;
  }
  return quatNormalize(a.map((v,i)=>wa*v+sign*wb*b[i]));
}
'''


def build(source):
    original=source.read_bytes()
    text=original.decode('utf-8').replace('\r\n','\n')
    payload_line=next(line for line in text.splitlines() if line.startswith('const payload = '))
    payload=json.loads(payload_line[len('const payload = '):].rstrip(';'))
    assert all(c['motion_fps']==60 and c['motion_frame_count']%2==1 for c in payload['clips']), 'Expected baked 60Hz data from 30Hz source.'
    def replace(before,after):
        nonlocal text
        assert text.count(before)==1, f'Viewer structure changed: {before[:80]}'
        text=text.replace(before,after,1)
    replace('<title>','<title>Unreal interpolation · ')
    replace('<button id="play">Play</button>', '<button id="play">Play</button>\n'
            '    <label>Interpolation <select id="comparisonInterpolation">'
            '<option value="unreal" selected>Unreal · Current</option>'
            '<option value="original">Original viewer · Slerp</option></select></label>')
    replace('<div class="pill" id="motionStatus">', '<div class="pill"><strong id="comparisonLabel">Unreal interpolation</strong></div>\n'
            '      <div class="pill" id="motionStatus">')
    replace('const motionStatus = document.getElementById("motionStatus");',
            'const comparisonInterpolation=document.getElementById("comparisonInterpolation");\n'
            'comparisonInterpolation.addEventListener("change",()=>{\n'
            '  document.getElementById("comparisonLabel").textContent=comparisonInterpolation.value==="unreal"?"Unreal interpolation":"Original viewer interpolation";\n'
            '  draw();\n});\nconst motionStatus = document.getElementById("motionStatus");')
    replace('function axesFromQuat(q){', UNREAL_ROTATION+'\nfunction axesFromQuat(q){')
    replace('''    const frameFloor=Math.floor(frameExact);
    const frame0=wrapIndex(frameFloor,clip.motion_frame_count);
    const frame1=(frame0+1)%clip.motion_frame_count;
    const alpha=frameExact-frameFloor;''', '''    const useUnreal=comparisonInterpolation.value==="unreal";
    // Odd baked frames already contain Slerp. Reconstruct directly from the
    // original 30Hz keys (even frames) so Unreal mode really replaces it.
    const stride=useUnreal?2:1;
    const frameFloor=Math.floor(frameExact/stride)*stride;
    const frame0=wrapIndex(frameFloor,clip.motion_frame_count);
    const span=Math.min(stride,clip.motion_frame_count-frame0);
    const frame1=(frame0+span)%clip.motion_frame_count;
    const alpha=(frameExact-frameFloor)/span;''')
    replace('axesFromQuat(quatSlerp(quatFromAxes(axes0),quatFromAxes(axes1),alpha))',
            'axesFromQuat((useUnreal?quatUnrealInterpolate:quatSlerp)(quatFromAxes(axes0),quatFromAxes(axes1),alpha))')
    replace('  frameExact,\n  playing,', '  frameExact,\n  interpolation:comparisonInterpolation.value,\n  playing,')
    dest=source.with_name('variant_viewer_unreal_interpolation.html')
    dest.write_text(text,encoding='utf-8')
    assert source.read_bytes()==original
    return dict(source=str(source),source_sha256=hashlib.sha256(original).hexdigest(),
                output=str(dest),output_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                policy_hz=30,display_hz=60,default_interpolation='Unreal Current',
                unchanged_motion_files=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--receipt',type=Path)
    args=p.parse_args();result=build(args.source)
    if args.receipt:args.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
