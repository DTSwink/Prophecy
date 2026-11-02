"""Local side-by-side, looping review of original and corrected targets."""
import json,pickle
import numpy as np
from scipy.spatial.transform import Rotation as R
from repair_slow_targets import Geometry,P,OUT,write

g=Geometry();clips=[]
for path in sorted((OUT/'candidates').glob('*.pkl')):
    data=np.load(path.with_suffix('.npz'));variants={}
    for key in ('before','after','wanted'):
        positions=[];quats=[]
        for f in data[key]:
            p,r=(f[:,:3,3],f[:,:3,:3]) if key=='wanted' else g.fk(f)
            g.set_pose(p,r);positions.append(g.d.geom_xpos.copy());quats.append(R.from_matrix(g.d.geom_xmat.reshape(-1,3,3)).as_quat())
        variants[key]=dict(p=np.round(positions,6).tolist(),q=np.round(quats,7).tolist())
    clips.append(dict(name=path.stem,frames=len(data['after']),fps=30,variants=variants))
write(OUT/'viewer-data.json',dict(geometry=g.gs,clips=clips))
html='''<!doctype html><html><head><meta charset="utf-8"><title>Slow loco target repair</title><style>
body{margin:0;background:#111923;color:#e6edf5;font:15px system-ui}header,footer{padding:12px 22px;display:flex;gap:20px;align-items:center}button,select{padding:8px;background:#25374b;color:white;border:1px solid #52677d;border-radius:5px}main{display:flex}section{width:50%;text-align:center}canvas{display:block;width:100%;height:65vh}input{flex:1}p{margin:12px 22px;color:#b6c6d9}h2{font-size:16px;font-weight:500}</style>
<script type="importmap">{"imports":{"three":"/Labs/MimicKitUEFN/vendor/three.module.js"}}</script></head><body>
<header><strong>Slow loco · target repair</strong><select id="clip"></select><label>Before: <select id="source"><option value="before">Previous robot target</option><option value="wanted">Original source with robot colliders</option></select></label></header>
<main><section><h2>Before</h2><canvas id="a"></canvas></section><section><h2>Corrected target</h2><canvas id="b"></canvas></section></main>
<footer><button id="play">Play</button><input id="time" type="range" min="0" value="0" step="1"><span id="frame"></span></footer>
<p>Space plays/pauses. Clips loop. Drag to orbit, scroll to zoom. Orange/gold: arms; grey: other colliders. This compares reference targets, not a learned policy rollout.</p>
<script type="module" src="viewer.js"></script></body></html>'''
(OUT/'index.html').write_text(html,encoding='utf-8')
js='''import * as T from 'three';import {OrbitControls} from '/Labs/MimicKitUEFN/vendor/OrbitControls.js';
const data=await (await fetch('viewer-data.json')).json();const select=document.querySelector('#clip'),source=document.querySelector('#source'),slider=document.querySelector('#time'),play=document.querySelector('#play');
data.clips.forEach(x=>select.add(new Option(x.name,x.name)));select.value='sitting';let frame=0,playing=false,last=0;
function make(id){const canvas=document.querySelector(id),renderer=new T.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(2,devicePixelRatio));const scene=new T.Scene();scene.background=new T.Color('#111923');const camera=new T.PerspectiveCamera(40,1,.01,50);camera.up.set(0,0,1);camera.position.set(2.5,-2,1.7);const controls=new OrbitControls(camera,canvas);controls.target.set(0,0,.5);controls.update();scene.add(new T.HemisphereLight(0xffffff,0x66717a,2));const light=new T.DirectionalLight(0xffffff,2);light.position.set(2,-3,5);scene.add(light);const grid=new T.GridHelper(6,30,0x43556b,0x263546);grid.rotation.x=Math.PI/2;scene.add(grid);
const meshes=data.geometry.map(g=>{let geo=g.type==='box'?new T.BoxGeometry(...g.size.map(x=>x*2)):new T.CapsuleGeometry(g.size[0],2*g.size[1],8,16);if(g.type!=='box')geo.rotateX(Math.PI/2);const arm=g.body.includes('arm')||g.body.includes('hand');const mat=new T.MeshStandardMaterial({color:arm?(g.body.startsWith('right')?0xe46a33:0xf0b23d):0x8696a8,roughness:.8});const mesh=new T.Mesh(geo,mat);scene.add(mesh);return mesh});return {canvas,renderer,scene,camera,controls,meshes};}
const views=[make('#a'),make('#b')];function clip(){return data.clips.find(x=>x.name===select.value)||data.clips[0];}
function draw(){const c=clip();frame=Math.min(c.frames-1,frame);slider.max=c.frames-1;slider.value=frame;document.querySelector('#frame').textContent=`Frame ${frame} / ${c.frames-1}`;views.forEach((v,index)=>{const a=c.variants[index?'after':source.value];v.meshes.forEach((m,i)=>{m.position.fromArray(a.p[frame][i]);m.quaternion.fromArray(a.q[frame][i]);});const w=v.canvas.clientWidth,h=v.canvas.clientHeight;v.renderer.setSize(w,h,false);v.camera.aspect=w/h;v.camera.updateProjectionMatrix();v.renderer.render(v.scene,v.camera);});}
function toggle(){playing=!playing;play.textContent=playing?'Pause':'Play';last=performance.now();}play.onclick=toggle;window.addEventListener('keydown',e=>{if(e.code==='Space'&&!['INPUT','SELECT'].includes(e.target.tagName)){e.preventDefault();toggle();}});select.onchange=()=>{frame=0;draw()};source.onchange=draw;slider.oninput=()=>{frame=+slider.value;draw()};views.forEach(v=>v.controls.addEventListener('change',draw));window.onresize=draw;
function animate(t){if(playing&&t-last>=1000/clip().fps){frame=(frame+Math.floor((t-last)*clip().fps/1000))%clip().frames;last=t;draw();}requestAnimationFrame(animate)}draw();requestAnimationFrame(animate);
'''
(OUT/'viewer.js').write_text(js,encoding='utf-8')
print(OUT/'index.html')
