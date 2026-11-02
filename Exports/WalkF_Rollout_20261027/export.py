"""Export a full fresh WalkF rollout through the existing viewer Actor pipeline."""
from pathlib import Path
import ctypes, hashlib, json, math, os, shutil, subprocess, sys

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[1]
STEPPER=Path(r'C:/Users/singerie/Documents/Cursor/stepper')
sys.path.insert(0,str(STEPPER/'training'))
os.environ.setdefault('OMP_NUM_THREADS','2')
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
import numpy as np
import torch
torch.set_num_threads(2)
torch.set_num_interop_threads(1)
import model_viewer_app as viewer

runtime=json.loads((PROJECT/'Content/locomotion/NN/prophecy_lower_body_runtime.json').read_text())
checkpoint=Path(runtime['checkpoint_path'])
source=STEPPER/'ue5/animations_omni_only/npz_final/M_Neutral_Walk_Loop_F.npz'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(checkpoint).lower()==runtime['checkpoint_sha256'].lower()
actor=viewer.Actor(actor_id=0,kind='model',name='WalkF / Run checkpoint',color='#f3a348',checkpoint_path=checkpoint)
actor.load_checkpoint(checkpoint,source,torch.device('cpu'))
actor.generate_to(actor.frame_count-1)
positions=np.asarray(actor.generated_pos,dtype=np.float32)
rotations=np.asarray(actor.generated_rot,dtype=np.float32)
names=list(actor.bone_names);parents=np.asarray(actor.parents,dtype=np.int32)
lower_names={'pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r'}
visible_indices=np.asarray([i for i,n in enumerate(names) if n in lower_names],dtype=np.int32)
with np.load(source,allow_pickle=False) as z:
    fps=float(z['fps']);source_count=int(z['frame_count'])
    root_index=list(z['bone_names']).index('root')
    source_roots=z['model_global_joint_pos_m'][:,root_index].copy()
assert len(positions)==source_count==actor.frame_count
assert rotations.shape==(source_count,len(names),3,3)
assert np.isfinite(positions).all() and np.isfinite(rotations).all()
identity=np.eye(3,dtype=np.float32)
orthogonality_error=float(np.max(np.abs(rotations.swapaxes(-1,-2)@rotations-identity)))
assert orthogonality_error<0.001
np.savez_compressed(OUT/'walkf_rollout.npz',
    positions_m=positions,rotations=rotations,bone_names=np.asarray(names),parents=parents,
    fps=np.asarray(fps),frame_indices=np.arange(source_count),
    visible_bone_indices=visible_indices,source_root_positions_m=source_roots,
    pin_states=np.asarray(actor.generated_pin_states,dtype=np.float32),
    pin_values=np.asarray(actor.generated_pin_values,dtype=np.float32),
    effective_pin_values=np.asarray(actor.generated_effective_pin_values,dtype=np.float32))
metadata={'checkpoint':str(checkpoint),'checkpoint_sha256':sha(checkpoint),
    'source':str(source),'source_sha256':sha(source),'viewer_source':str(Path(viewer.__file__)),
    'viewer_source_sha256':sha(Path(viewer.__file__)),'fps':fps,'frame_count':source_count,
    'first_frame':0,'last_frame':source_count-1,'pose_span_seconds':(source_count-1)/fps,
    'seed_frames':[0,1],'inferred_frames':[2,source_count-1],'bones':names,
    'visible_bones':[names[i] for i in visible_indices],'body_mode':actor.cfg.body_mode,
    'body_mask_note':'This is a lower-body policy; preview matches the viewer lower-body mask. Other raw FK slots are retained only for completeness.',
    'coordinates':'Viewer world coordinates, metres, Y up; rotations are 3x3 world matrices.',
    'pin_constraint':actor.pin_constraint_enabled,'run_near_floor_pin':actor.run_near_floor_pin_enabled,
    'device':'cpu','orthogonality_max_error':orthogonality_error,
    'method':'Fresh deterministic rollout via unchanged Model Viewer Actor.load_checkpoint and generate_to; not a live window-memory capture.',
    'preview':'Rendered from the saved poses, with two following cameras. World motion is retained in NPZ.'}
(OUT/'metadata.json').write_text(json.dumps(metadata,indent=2))
print(json.dumps({'stage':'rollout_saved','frames':source_count,'bones':len(names),'fps':fps}),flush=True)

from PIL import Image,ImageDraw,ImageFont
fontpath=Path('C:/Windows/Fonts/segoeui.ttf')
font=ImageFont.truetype(str(fontpath),19);small=ImageFont.truetype(str(fontpath),15)
titlefont=ImageFont.truetype(str(fontpath),27)
W,H=1280,720
light=np.array([-0.4,0.8,-0.4]);light/=np.linalg.norm(light)
def cylinder(a,b,r,color):
    axis=b-a;length=float(np.linalg.norm(axis))
    if length<1e-6:return []
    axis/=length;seed=np.array([0.,1.,0.])
    if abs(axis@seed)>.9:seed=np.array([1.,0.,0.])
    u=np.cross(axis,seed);u/=np.linalg.norm(u);v=np.cross(axis,u)
    ring=np.array([math.cos(t)*u+math.sin(t)*v for t in np.linspace(0,2*math.pi,11)[:-1]])*r
    faces=[]
    for j in range(10):faces.append((np.array([a+ring[j],b+ring[j],b+ring[(j+1)%10],a+ring[(j+1)%10]]),color))
    faces.append((a+ring,color));faces.append((b+ring,color))
    return faces
def ellipsoid(center,axes,radii,color):
    verts=[];faces=[]
    for lat in np.linspace(-math.pi/2,math.pi/2,8):
        verts.append([center+axes@(np.array([math.cos(lat)*math.cos(lon),math.sin(lat),math.cos(lat)*math.sin(lon)])*radii) for lon in np.linspace(0,2*math.pi,13)[:-1]])
    for i in range(7):
        for j in range(12):faces.append((np.array([verts[i][j],verts[i][(j+1)%12],verts[i+1][(j+1)%12],verts[i+1][j]]),color))
    return faces
idx={n:i for i,n in enumerate(names)}
pelvis=idx['pelvis']
def model_faces(pos,rot):
    faces=[];base=(239,161,74)
    for j,name in enumerate(names):
        parent=int(parents[j])
        if name not in lower_names:continue
        if parent<0 or any(s in name for s in ('spine','clavicle','neck','head','ball','finger')):continue
        if name.startswith('thigh'):radius=.072
        elif name.startswith('calf'):radius=.065
        elif name.startswith('foot'):radius=.047
        elif name.startswith('upperarm'):radius=.046
        elif name.startswith('lowerarm'):radius=.042
        elif name.startswith('hand'):radius=.031
        else:continue
        color=base if name.endswith('_l') else (214,135,58)
        faces.extend(cylinder(pos[parent],pos[j],radius,color))
        faces.extend(ellipsoid(pos[j],np.eye(3),np.array([radius]*3),color))
    faces.extend(ellipsoid(pos[pelvis],np.eye(3),np.array([.14,.085,.085]),(223,145,65)))
    for side in ('l','r'):
        foot=idx.get('foot_'+side);ball=idx.get('ball_'+side)
        if foot is not None and ball is not None:
            faces.extend(cylinder(pos[foot],pos[ball],.045,base))
    return faces
def render_frame(frame):
    im=Image.new('RGB',(W,H),(14,20,30));draw=ImageDraw.Draw(im)
    draw.text((32,20),'WalkF | Run checkpoint',font=titlefont,fill=(235,241,248))
    draw.text((980,29),f'Frame {frame:03d} / {source_count-1}   {frame/fps:.2f}s',font=font,fill=(173,195,215))
    draw.line((640,92,640,655),fill=(39,54,72),width=1)
    pos=positions[frame];rot=rotations[frame];faces=model_faces(pos,rot)
    for view,(yaw,label) in enumerate([(-.65,'Three-quarter view'),(-math.pi/2,'Side view')]):
        pane=Image.new('RGB',(W,H),(14,20,30));draw=ImageDraw.Draw(pane)
        pitch=.16;forward=np.array([math.sin(yaw)*math.cos(pitch),-math.sin(pitch),math.cos(yaw)*math.cos(pitch)])
        right=np.array([math.cos(yaw),0.,-math.sin(yaw)]);up=np.cross(forward,right)
        target=np.array([pos[pelvis,0],.55,pos[pelvis,2]])
        cx=320+view*640;cy=375;scale=390
        def project(p):
            d=p-target
            return np.stack([cx+(d@right)*scale,cy-(d@up)*scale],axis=-1)
        centerx=round(float(target[0])*2)/2;centerz=round(float(target[2])*2)/2
        for s in np.arange(-2.5,2.51,.5):
            for a,b in [(np.array([centerx+s,0,centerz-2.5]),np.array([centerx+s,0,centerz+2.5])),(np.array([centerx-2.5,0,centerz+s]),np.array([centerx+2.5,0,centerz+s]))]:
                q=project(np.array([a,b]));draw.line(tuple(map(tuple,q)),fill=(32,48,64),width=1)
        ordered=sorted(faces,key=lambda f:-float((f[0].mean(axis=0)-target)@forward))
        for vertices,color in ordered:
            q=project(vertices)
            n=np.cross(vertices[1]-vertices[0],vertices[2]-vertices[0]);norm=np.linalg.norm(n)
            brightness=.55+.45*max(0,float(n@light/max(norm,1e-9)))
            shade=tuple(int(c*brightness) for c in color)
            draw.polygon([tuple(p) for p in q],fill=shade)
        draw.rectangle((view*640+20,74,view*640+620,104),fill=(14,20,30))
        draw.text((view*640+32,78),label,font=small,fill=(146,174,199))
        im.paste(pane.crop((view*640,74,(view+1)*640,654)),(view*640,74))
    draw=ImageDraw.Draw(im)
    draw.line((640,92,640,654),fill=(39,54,72),width=1)
    draw.rectangle((0,654,W,H),fill=(14,20,30))
    draw.text((32,670),'Full source sequence | 30 fps | Lower-body policy | Original viewer inference',font=small,fill=(163,184,204))
    draw.line((32,707,W-32,707),fill=(42,58,76),width=4)
    draw.line((32,707,32+(W-64)*frame/(source_count-1),707),fill=(239,161,74),width=4)
    return im
ffmpeg=shutil.which('ffmpeg');assert ffmpeg,'ffmpeg missing'
video=OUT/'walkf_rollout.mp4'
cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(video)]
proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
for frame in range(source_count):
    image=render_frame(frame)
    if frame==source_count//2:image.save(OUT/'preview.jpg',quality=88)
    proc.stdin.write(image.tobytes())
proc.stdin.close();assert proc.wait()==0
metadata['files']={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in [OUT/'walkf_rollout.npz',video]}
(OUT/'metadata.json').write_text(json.dumps(metadata,indent=2))
(OUT/'README.txt').write_text('WalkF complete rollout, 27 October 2026\n\nwalkf_rollout.mp4: two-camera rendered preview of the full 121-frame sequence.\nwalkf_rollout.npz: world positions and rotations, skeleton, body mask and pin values.\nmetadata.json: source/checkpoint hashes, settings and coordinate conventions.\n\nGenerated fresh through the unmodified Model Viewer inference pipeline using\nits default Pin Constraint and Run near-floor pin settings. The open viewer\nwas not altered. This is a rendered export, not a screen recording or a dump\nof unsaved in-memory UI tweaks. Frames 0/1 seed the autoregressive rollout;\nframes 2 through 120 are inferred. Preview cameras follow horizontal motion;\nNPZ retains the actual world-space translation. This is a LOWER-BODY policy:\nuse visible_bone_indices for the nine meaningful pelvis/leg/foot joints. Other\nraw FK slots are retained only for completeness, not a valid upper-body motion.\n')
print(json.dumps({'stage':'complete','folder':str(OUT),'bytes':sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())}),flush=True)
