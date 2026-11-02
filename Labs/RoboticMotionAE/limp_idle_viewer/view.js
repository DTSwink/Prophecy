import * as T from 'three';
import {OrbitControls} from '/Labs/MimicKitUEFN/vendor/OrbitControls.js';
const data=await(await fetch('data.json',{cache:'no-store'})).json(),$=id=>document.getElementById(id);
let time=0,playing=false,last=null,raf=0,syncing=false;
const views=data.clips.map((clip,i)=>{
 const id=i?'b':'a',canvas=$(id),renderer=new T.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
 const scene=new T.Scene();scene.background=new T.Color('#101821');const camera=new T.PerspectiveCamera(38,1,.01,50);camera.up.set(0,0,1);const controls=new OrbitControls(camera,canvas);
 scene.add(new T.HemisphereLight(0xffffff,0x718598,2.2));const light=new T.DirectionalLight(0xffffff,2.5);light.position.set(2,-3,5);scene.add(light);
 const grid=new T.GridHelper(5,50,0x718b91,0x2a3e4e);grid.rotation.x=Math.PI/2;scene.add(grid);
 const floor=new T.Mesh(new T.PlaneGeometry(5,5),new T.MeshStandardMaterial({color:0x1c2b38,roughness:1,side:T.DoubleSide}));floor.position.z=-.004;scene.add(floor);
 const meshes=data.geometry.map(g=>{const shape=g.type==='box'?new T.BoxGeometry(...g.size.map(v=>v*2)):new T.CapsuleGeometry(g.size[0],g.size[1]*2,8,16);if(g.type!=='box')shape.rotateX(Math.PI/2);
 const passive=g.body.startsWith(clip.report.disabled_leg+'_')&&/(thigh|shin|foot)$/.test(g.body);const color=g.body===clip.active_foot?0x60cda0:passive?0x596c7b:0xe1ad77;
 const mesh=new T.Mesh(shape,new T.MeshStandardMaterial({color,roughness:.77}));scene.add(mesh);return mesh;});
 const polygon=new T.LineLoop(new T.BufferGeometry(),new T.LineBasicMaterial({color:0x62dba7,depthTest:false}));polygon.renderOrder=2;scene.add(polygon);
 const marker=new T.Mesh(new T.SphereGeometry(.012,14,10),new T.MeshBasicMaterial({color:0xffa65e,depthTest:false}));marker.renderOrder=3;scene.add(marker);
 $(id+'-source').textContent=`${clip.active_foot.startsWith('right')?'Right':'Left'} foot support · source frame ${clip.report.source_frame}`;
 return{id,clip,canvas,renderer,scene,camera,controls,meshes,polygon,marker};
});
function draw(){
 $('time').value=time;$('clock').textContent=`${time.toFixed(2)} / ${data.duration.toFixed(2)} s`;
 for(const v of views){const clip=v.clip.variants[$('breathing').checked?'breathing':'still'],x=Math.min(time*clip.fps,clip.rows.length-1),i=Math.floor(x),a=clip.rows[i],b=clip.rows[Math.min(i+1,clip.rows.length-1)],t=x-i;
 v.meshes.forEach((m,k)=>{m.position.fromArray(a.p[k]).lerp(new T.Vector3().fromArray(b.p[k]),t);m.quaternion.fromArray(a.q[k]).slerp(new T.Quaternion().fromArray(b.q[k]),t);});
 v.polygon.geometry.dispose();v.polygon.geometry=new T.BufferGeometry().setFromPoints(a.support.map(p=>new T.Vector3(p[0],p[1],.004)));
 v.marker.position.fromArray(a.com).lerp(new T.Vector3().fromArray(b.com),t);v.marker.position.z=.015;v.polygon.visible=v.marker.visible=$('support').checked;
 $(v.id+'-info').textContent=`COM inside active foot by ${(T.MathUtils.lerp(a.margin,b.margin,t)*100).toFixed(1)} cm · feet fixed`;
 const w=v.canvas.clientWidth,h=v.canvas.clientHeight;v.renderer.setSize(w,h,false);v.camera.aspect=w/h;v.camera.updateProjectionMatrix();v.renderer.render(v.scene,v.camera);
 }
}
function camera(mode){syncing=true;for(const v of views){v.controls.target.set(-.06,0,.86);v.camera.position.fromArray(mode==='front'?[3.4,0,1.55]:mode==='side'?[0,-3.4,1.5]:[2.65,-2.65,1.8]);v.controls.update();}syncing=false;draw();}
for(const v of views)v.controls.addEventListener('change',()=>{if(syncing)return;syncing=true;for(const other of views)if(other!==v){other.camera.position.copy(v.camera.position);other.controls.target.copy(v.controls.target);other.controls.update();}syncing=false;draw();});
function animate(now){if(!playing)return;const elapsed=last===null?0:Math.max(0,(now-last)/1000);last=now;time=(time+elapsed*Number($('speed').value))%data.duration;draw();raf=requestAnimationFrame(animate);}
function toggle(){playing=!playing;$('play').textContent=playing?'Pause':'Play';$('play').setAttribute('aria-pressed',String(playing));cancelAnimationFrame(raf);last=null;if(playing)raf=requestAnimationFrame(animate);}
$('play').onclick=toggle;window.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();if(!e.repeat)toggle();}},true);
$('time').max=data.duration;$('time').oninput=()=>{time=+$('time').value;last=null;draw();};$('breathing').onchange=draw;$('support').onchange=draw;
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>camera(b.dataset.view));window.addEventListener('resize',draw);
$('details').textContent=`${data.duration.toFixed(2)}-second seamless idle loop | pelvis moving, feet pinned with IK | joint-limit and collider checks passed.`;
// Read-only diagnostic surface for headless playback verification.
window.idlePreview={get time(){return time;},get playing(){return playing;},duration:data.duration,views};
camera('three');
