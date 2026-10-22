import * as T from 'three';
import {OrbitControls} from '/OrbitControls.js';
const $=id=>document.getElementById(id),canvas=$('view');
const renderer=new T.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));
const scene=new T.Scene();scene.background=new T.Color('#101820');
const cam=new T.PerspectiveCamera(42,1,.02,100);cam.up.set(0,0,1);
const controls=new OrbitControls(cam,canvas);controls.enableDamping=false;
scene.add(new T.HemisphereLight(0xd6ecff,0x46515c,2.2));const sun=new T.DirectionalLight(0xfff2df,2.7);sun.position.set(3,-4,7);scene.add(sun);
const grid=new T.GridHelper(30,60,0x476779,0x223441);grid.rotation.x=Math.PI/2;scene.add(grid);
const parts=[],meshes=[],arrow=new T.ArrowHelper(new T.Vector3(0,1,0),new T.Vector3(),.55,0x8cead0,.11,.06);scene.add(arrow);
let state=null,info=null,timer=null,busy=false,playing=false,lastKick=null,nextFrame=0,renderCount=0,wantsPlay=false;
window.liveVizDiagnostics=()=>({playing,tick:state?.tick,renderCount,timer:timer!==null});
function label(s){return s.replaceAll('_',' ').replace(/\b\w/g,x=>x.toUpperCase())}
function direction(){return $('direction').value.split(',').map(Number)}
function selected(){return info?.bodies.findIndex(b=>b.name===$('limb').value)??-1}
function draw(){
 if(!state)return;
 const i=selected();parts.forEach((part,j)=>{part.position.fromArray(state.pose[j]);part.quaternion.fromArray(state.pose[j],3);part.children.forEach(m=>m.material.color.setHex(j===i?0x7fdfc9:0xe9a368))});
 if(i>=0){arrow.position.copy(parts[i].position);arrow.setDirection(new T.Vector3(...direction()));arrow.setLength(.3+Math.min(+$('strength').value,5)*.08,.10,.05)}
 const w=canvas.clientWidth,h=canvas.clientHeight;renderer.setSize(w,h,false);cam.aspect=w/h;cam.updateProjectionMatrix();renderer.render(scene,cam);renderCount++;
}
controls.addEventListener('change',draw);new ResizeObserver(draw).observe(canvas);
function resetCamera(){const p=state?state.pose[0]:[0,0,1];cam.position.set(p[0]+3.2,p[1]-4.2,2.1);controls.target.set(p[0],p[1],.85);controls.update();draw()}
async function api(cmd,payload={}){
 const response=await fetch('/api/'+cmd,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
 const result=await response.json();if(!response.ok)throw Error(result.error||response.statusText);return result;
}
function update(s){
 state=s;playing=wantsPlay&&!s.paused;$('status').textContent=playing?'Live':'Paused';$('status').classList.toggle('live',playing);$('play').textContent=playing?'Pause':'Resume';$('kick').disabled=!playing;
 $('clock').textContent=s.seconds.toFixed(2)+' s';$('rate').textContent=playing?'30 Hz policy':'No simulation work';$('selection').textContent=label($('limb').value);
 if(s.last_kick&&JSON.stringify(s.last_kick)!==lastKick){lastKick=JSON.stringify(s.last_kick);$('last').textContent='Applied '+s.last_kick.measured_m_s.toFixed(2)+' m/s to selected limb.'}
 draw();
}
function fail(e){wantsPlay=false;playing=false;clearTimeout(timer);timer=null;$('error').textContent=String(e);api('pause').then(update).catch(()=>{});}
async function loop(){
 timer=null;if(!playing||busy||document.hidden)return;busy=true;
 try{const s=await api('step');update(s);}catch(e){fail(e)}finally{busy=false;}
 if(playing&&wantsPlay){nextFrame+=1000/30;const now=performance.now();if(nextFrame<now-100)nextFrame=now;timer=setTimeout(loop,Math.max(0,nextFrame-now))}
}
async function pause(){wantsPlay=false;playing=false;clearTimeout(timer);timer=null;update(await api('pause'));}
$('play').onclick=async()=>{try{if(playing)await pause();else{wantsPlay=true;update(await api('play'));nextFrame=performance.now();loop();}}catch(e){fail(e)}};
$('reset').onclick=async()=>{try{update(await api('reset',{drawn:$('equipment').value==='1'}));lastKick=null;$('last').textContent='Reset to idle.';resetCamera();}catch(e){fail(e)}};
$('equipment').onchange=()=>$('reset').click();
$('kick').onclick=async()=>{try{const strength=+$('strength').value;if(!Number.isFinite(strength)||strength<.1||strength>10)throw Error('Use a strength between 0.1 and 10 m/s.');await api('impulse',{body:$('limb').value,direction:direction(),strength});$('last').textContent='Impulse queued…';}catch(e){fail(e)}};
for(const id of ['limb','direction'])$(id).onchange=()=>{if(state)update(state)};
$('strength').oninput=()=>{$('slider').value=$('strength').value;draw()};$('slider').oninput=()=>{$('strength').value=$('slider').value;draw()};$('camera').onclick=resetCamera;
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause().catch(fail)});
window.addEventListener('pagehide',()=>{fetch('/api/pause',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',keepalive:true}).catch(()=>{})});
document.addEventListener('keydown',e=>{if(/INPUT|SELECT|BUTTON/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();$('play').click()}else if(e.code==='Enter'&&playing)$('kick').click()});
let down=null;canvas.addEventListener('pointerdown',e=>down=[e.clientX,e.clientY]);canvas.addEventListener('pointerup',e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;const r=canvas.getBoundingClientRect(),ray=new T.Raycaster();ray.setFromCamera(new T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),cam);const hit=ray.intersectObjects(meshes)[0];if(hit){$('limb').value=hit.object.userData.body;update(state)}});
try{
 info=await(await fetch('/api/info')).json();
 for(const body of info.bodies){const part=new T.Group();scene.add(part);parts.push(part);$('limb').add(new Option(label(body.name),body.name));for(const s of body.shapes){let g;if(s.type==='box')g=new T.BoxGeometry(...s.size.map(x=>2*x));else if(s.type==='capsule'){g=new T.CapsuleGeometry(s.size[0],2*s.size[1],6,12);g.rotateX(Math.PI/2)}else g=new T.SphereGeometry(s.size[0],16,12);const mesh=new T.Mesh(g,new T.MeshStandardMaterial({color:0xe9a368,roughness:.65}));mesh.position.fromArray(s.pos);mesh.quaternion.set(s.quat[1],s.quat[2],s.quat[3],s.quat[0]);mesh.userData.body=body.name;part.add(mesh);meshes.push(mesh)}}
 $('limb').value='right_hand';$('checkpoint').textContent='Frozen checkpoint '+info.checkpoint.key.split('/').at(-1).replace('.zip','').replace('checkpoint_','')+' · Local CPU simulation · '+info.physics_hz+' Hz physics';
 update(await(await fetch('/api/state')).json());$('play').disabled=false;$('reset').disabled=false;resetCamera();
}catch(e){fail(e)}
