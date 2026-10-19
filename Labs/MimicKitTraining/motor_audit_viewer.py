"""Publish isolated audit traces to a local read-only viewer, no trainer edits."""
import json,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/MimicKitMotorAudit'
tree=ET.parse(OUT/'source/assets/uefn/humanoid_uefn.xml')
bodies=[]
for body in tree.findall('.//body'):
    shapes=[]
    for g in body.findall('geom'):
        shapes.append(dict(type=g.get('type'),size=list(map(float,g.get('size').split())),
            pos=list(map(float,g.get('pos','0 0 0').split())),quat=list(map(float,g.get('quat','1 0 0 0').split()))))
    bodies.append(dict(name=body.get('name'),shapes=shapes))
# XML tree order equals the deployed kinematic body's DFS order.
assert len(bodies)==15
runs=[]
expanded='search_forward'
for candidate in ['search_forward_matched','search_forward_windowed']:
    record=OUT/(candidate+'.json')
    if record.exists() and json.loads(record.read_text())['passed']:expanded=candidate
for file,title,world in [('policy_stock_traces','Original policy · original command range',4),
                         ('search_forward_stock','Command search · original motors and command range',0),
                         (expanded,'Command search · original motors · wider commands',0)]:
    p=OUT/(file+'.npz')
    if not p.exists():continue
    data=np.load(p);report_path=OUT/(file.replace('_traces','')+'.json')
    report=json.loads(report_path.read_text())
    if file.endswith('_traces'):
        row=report['rows'][world];count=max(1,round(row['seconds']*30));passed=row['passed']
    else:count=len(data['pose']);passed=report['passed']
    runs.append(dict(name=title,pose=data['pose'][:count,world].round(6).tolist(),
        target=data['target'][:count,world].round(6).tolist(),passed=passed,seconds=count/30,
        note='Physical rollout; fixed gains and torque caps. No root forces, teleporting or pinned feet. Search controller is diagnostic, not a trained replacement.'))
(OUT/'viewer-data.json').write_text(json.dumps(dict(bodies=bodies,runs=runs),separators=(',',':')))
html=r'''<!doctype html><meta charset="utf-8"><title>Motor authority test</title>
<style>body{margin:0;background:#10151d;color:#e2eaf2;font:14px system-ui}nav,footer{display:flex;gap:15px;align-items:center;padding:12px}select,button{color:inherit;background:#203041;border:1px solid #53647a;padding:8px;border-radius:4px}canvas{width:100%;height:78vh;display:block}#stats{position:absolute;left:18px;top:65px;white-space:pre;font:13px monospace;pointer-events:none}input[type=range]{flex:1}small{display:block;padding:0 12px;color:#adbfd2}</style>
<nav><strong>Motor authority · Run forward</strong><select id="run"></select><label><input type="checkbox" id="target" checked> Target</label><button id="camera">Reset camera</button></nav>
<div id="stats"></div><canvas id="view"></canvas><footer><button id="play">Pause</button><input id="time" type="range" min="0" step="1" value="0"><span id="clock"></span></footer><small id="note"></small>
<script type="importmap">{"imports":{"three":"/Labs/MimicKitUEFN/vendor/three.module.js"}}</script>
<script type="module">
import * as T from 'three';import {OrbitControls} from '/Labs/MimicKitUEFN/vendor/OrbitControls.js';
const data=await(await fetch('viewer-data.json')).json(),canvas=document.querySelector('#view'),pick=document.querySelector('#run'),time=document.querySelector('#time'),stats=document.querySelector('#stats');
const scene=new T.Scene();scene.background=new T.Color('#10151d');const cam=new T.PerspectiveCamera(42,1,.02,200);cam.up.set(0,0,1);
const renderer=new T.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));
scene.add(new T.HemisphereLight(0xdfefff,0x354050,2));const light=new T.DirectionalLight(0xffffff,2);light.position.set(3,-4,7);scene.add(light);
const grid=new T.GridHelper(200,200,0x51667c,0x263848);grid.rotation.x=Math.PI/2;scene.add(grid);
const controls=new OrbitControls(cam,canvas);controls.enableDamping=true;
function rig(color,opacity){const root=new T.Group(),parts=[];scene.add(root);for(const body of data.bodies){const part=new T.Group();root.add(part);parts.push(part);for(const s of body.shapes){let geom;if(s.type==='box')geom=new T.BoxGeometry(...s.size.map(x=>2*x));else if(s.type==='capsule'){geom=new T.CapsuleGeometry(s.size[0],2*s.size[1],6,12);geom.rotateX(Math.PI/2);}else geom=new T.SphereGeometry(s.size[0],12,10);const mesh=new T.Mesh(geom,new T.MeshStandardMaterial({color,transparent:opacity<1,opacity,depthWrite:opacity===1,roughness:.75}));mesh.position.fromArray(s.pos);mesh.quaternion.set(s.quat[1],s.quat[2],s.quat[3],s.quat[0]);part.add(mesh);}}return {root,parts};}
const actual=rig(0xf58c37,1),target=rig(0xe63bbd,.3);let run,frame=0,playing=true,last=performance.now(),lastRoot=new T.Vector3(),dirty=true;
controls.addEventListener('change',()=>dirty=true);window.addEventListener('resize',()=>dirty=true);
for(let i=0;i<data.runs.length;i++)pick.add(new Option(data.runs[i].name,i));
function camera(){const r=run.pose[0][0];controls.target.set(r[0],r[1],.8);cam.position.set(r[0]+3,r[1]-4,2);controls.update();lastRoot.set(r[0],r[1],r[2]);}
function load(){run=data.runs[+pick.value];frame=0;dirty=true;time.max=run.pose.length-1;document.querySelector('#note').textContent=run.note;camera();}pick.onchange=load;
document.querySelector('#camera').onclick=camera;document.querySelector('#target').onchange=e=>{target.root.visible=e.target.checked;dirty=true;};
document.querySelector('#play').onclick=e=>{playing=!playing;dirty=true;e.target.textContent=playing?'Pause':'Play';};time.oninput=()=>{frame=+time.value;dirty=true;};
function pose(rig,p){for(let i=0;i<15;i++){rig.parts[i].position.fromArray(p[i]);rig.parts[i].quaternion.fromArray(p[i],3);}}
load();const completed=data.runs.map((r,i)=>({r,i})).filter(x=>x.r.passed).sort((a,b)=>b.r.seconds-a.r.seconds);pick.value=String(completed.length?completed[0].i:0);load();
function draw(now){
const dt=Math.max(0,Math.min((now-last)/1000,.1));last=now;if(playing){frame=(frame+30*dt)%run.pose.length;dirty=true;}
const index=Math.floor(frame),root=new T.Vector3().fromArray(run.pose[index][0]);let delta=root.clone().sub(lastRoot);delta.z=0;cam.position.add(delta);controls.target.add(delta);lastRoot.copy(root);controls.update();
if(dirty){pose(actual,run.pose[index]);pose(target,run.target[index]);const w=canvas.clientWidth,h=canvas.clientHeight;renderer.setSize(w,h,false);cam.aspect=w/h;cam.updateProjectionMatrix();renderer.render(scene,cam);time.value=index;document.querySelector('#clock').textContent=((index+1)/30).toFixed(2)+' / '+run.seconds.toFixed(2)+' s';stats.textContent='Orange  physical agent\nMagenta  actual training target\nRecorded result  '+(run.passed?'completed tested duration':'early termination')+'\nFrame  '+(index+1);dirty=false;}
requestAnimationFrame(draw);}requestAnimationFrame(draw);
</script>'''
(OUT/'index.html').write_text(html,encoding='utf-8')
print(json.dumps(dict(runs=[r['name'] for r in runs],url='http://127.0.0.1:8843/Saved/MimicKitMotorAudit/')))
