import * as T from 'three';
import {OrbitControls} from '/Labs/MimicKitUEFN/vendor/OrbitControls.js';
const data=await(await fetch('view-data.json',{cache:'no-store'})).json();
const slider=document.querySelector('#time'),play=document.querySelector('#play');
let frame=20,playing=false,last=0,syncing=false;
function make(id){
 const canvas=document.querySelector('#'+id),renderer=new T.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));
 const scene=new T.Scene();scene.background=new T.Color('#101821');
 const camera=new T.PerspectiveCamera(38,1,.01,30);camera.up.set(0,0,1);
 const controls=new OrbitControls(camera,canvas);controls.target.set(.12,.025,.35);camera.position.set(1.7,.8,1.0);controls.update();
 scene.add(new T.HemisphereLight(0xffffff,0x647482,2));const light=new T.DirectionalLight(0xffffff,2);light.position.set(2,3,5);scene.add(light);
 const grid=new T.GridHelper(4,40,0x516273,0x243442);grid.rotation.x=Math.PI/2;scene.add(grid);
 const meshes=data.geometry.map((g,i)=>{
  let geometry=g.type==='box'?new T.BoxGeometry(...g.size.map(x=>2*x)):new T.CapsuleGeometry(g.size[0],2*g.size[1],12,24);
  if(g.type!=='box')geometry.rotateX(Math.PI/2);
  const arm=g.body.includes('arm')||g.body.includes('hand');
  const material=new T.MeshStandardMaterial({color:arm?(g.body.startsWith('right')?0xe46a33:0xf0b23d):0x8b9aa9,roughness:.8,opacity:1,transparent:false,depthTest:true,depthWrite:true});
  const mesh=new T.Mesh(geometry,material);mesh.name=g.name;scene.add(mesh);return mesh;
 });
 return {id,canvas,renderer,scene,camera,controls,meshes,select:document.querySelector('#'+id+'-type')};
}
const views=[make('a'),make('b')];
function hasDraft(){return data.draft_frame!==undefined&&views.some(v=>v.select.value==='draft')}
function draw(){
 if(hasDraft()){frame=data.draft_frame;playing=false;play.textContent='Play'}
 slider.disabled=play.disabled=hasDraft();slider.max=data.frames-1;slider.value=frame;
 document.querySelector('#frame').textContent=`Frame ${frame} / ${data.frames-1}`;
 for(const v of views){
  const a=data.variants[v.select.value][hasDraft()&&v.select.value==='draft'?0:frame];
  v.meshes.forEach((m,i)=>{m.position.fromArray(a.p[i]);m.quaternion.fromArray(a.q[i]);m.updateMatrixWorld()});
  document.querySelector('#'+v.id+'-info').textContent=`Arm/leg overlap ${a.arm_leg_penetration_cm.toFixed(2)} cm`;
  const w=v.canvas.clientWidth,h=v.canvas.clientHeight;v.renderer.setSize(w,h,false);v.camera.aspect=w/h;v.camera.updateProjectionMatrix();v.renderer.render(v.scene,v.camera);
 }
}
for(const v of views){
 v.controls.addEventListener('change',()=>{if(syncing)return;syncing=true;for(const other of views)if(other!==v){other.camera.position.copy(v.camera.position);other.camera.quaternion.copy(v.camera.quaternion);other.controls.target.copy(v.controls.target);other.controls.update()}syncing=false;draw()});
 v.select.onchange=draw;
}
function toggle(){if(hasDraft())return;playing=!playing;play.textContent=playing?'Pause':'Play';last=performance.now()}
play.onclick=toggle;slider.oninput=()=>{frame=+slider.value;draw()};
window.addEventListener('keydown',e=>{if(e.code==='Space'&&e.target.tagName!=='SELECT'){e.preventDefault();toggle()}});
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{
 const positions={front:[1.8,0,.8],left:[.15,-1.7,.8],right:[.15,1.7,.8],back:[-1.5,0,.8]};
 syncing=true;views.forEach(v=>{v.controls.target.set(.12,.025,.35);v.camera.position.fromArray(positions[b.dataset.view]);v.controls.update()});syncing=false;draw();
});
document.querySelector('#depthcheck').onclick=()=>{
 const results=views.map(v=>{
  const w=512,h=512,target=new T.WebGLRenderTarget(w,h,{depthBuffer:true,samples:0});
  const a=new Uint8Array(w*h*4),b=new Uint8Array(a.length);v.renderer.setRenderTarget(target);
  v.meshes.forEach((m,i)=>m.renderOrder=i+1);v.renderer.render(v.scene,v.camera);v.renderer.readRenderTargetPixels(target,0,0,w,h,a);
  v.meshes.forEach((m,i)=>m.renderOrder=v.meshes.length-i);v.renderer.render(v.scene,v.camera);v.renderer.readRenderTargetPixels(target,0,0,w,h,b);
  let different=0;for(let i=0;i<a.length;i++)if(a[i]!==b[i])different++;
  v.meshes.forEach(m=>m.renderOrder=0);v.renderer.setRenderTarget(null);target.dispose();
  return different;
 });
 document.querySelector('#depth').textContent=`Reverse draw order: ${results.join(' / ')} changed color channels`;draw();
};
window.addEventListener('resize',draw);
function animate(t){if(playing&&t-last>=1000/30){frame=(frame+Math.floor((t-last)*30/1000))%data.frames;last=t;draw()}requestAnimationFrame(animate)}
draw();requestAnimationFrame(animate);
