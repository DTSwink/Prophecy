import * as T from 'three';
import {OrbitControls} from '/Labs/MimicKitUEFN/vendor/OrbitControls.js';
import {TransformControls} from './vendor/TransformControls.js';
import {fk,setWorldRotation,solveIK,rotatePelvisKeepingFeet,chains} from './kinematics.js';
const $=s=>document.querySelector(s),m=await(await fetch('/api/model')).json();
const labels=['Pelvis','Torso / chest','Head','Right upper arm','Right elbow / forearm','Right hand','Left upper arm','Left elbow / forearm','Left hand','Right thigh','Right knee / shin','Right foot','Left thigh','Left knee / shin','Left foot'];
const draftKey='slowloco-pose-editor:'+m.base_sha256;let frame=m.base.slice(),selected=1,mode='rotate',undo=[],redo=[],saved=m.saved,dragBase=null,dragPins=null,changed=false,validationTimer=null,validationVersion=0,pelvisLimited=false;
if(saved?.base_sha256!==m.base_sha256)saved=null;
function isChanged(){const reference=saved?.frame||m.base;return frame.some((x,i)=>Math.abs(x-reference[i])>1e-10)}
try{const local=JSON.parse(localStorage.getItem(draftKey));if(local?.frame?.length===40&&local.frame.every(Number.isFinite)){frame=local.frame;changed=isChanged()}}catch{}
const canvas=$('#scene'),renderer=new T.WebGLRenderer({canvas,antialias:true,alpha:false,depth:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));
const scene=new T.Scene();scene.background=new T.Color('#101923');
const camera=new T.PerspectiveCamera(38,1,.01,30);camera.up.set(0,0,1);camera.position.set(1.7,1.2,1.0);
const orbit=new OrbitControls(camera,canvas);orbit.target.set(.13,.025,.35);orbit.enableDamping=false;orbit.update();
scene.add(new T.HemisphereLight(0xffffff,0x647482,2));const light=new T.DirectionalLight(0xffffff,2);light.position.set(2,3,5);scene.add(light);
const grid=new T.GridHelper(4,40,0x536578,0x26394a);grid.rotation.x=Math.PI/2;grid.material.depthTest=true;grid.material.depthWrite=true;scene.add(grid);
const root=new T.Group();scene.add(root);const reference=new T.Group();reference.visible=false;scene.add(reference);
const meshes=m.geometry.map((g,i)=>{
 const geometry=g.type==='box'?new T.BoxGeometry(...g.size.map(x=>2*x)):new T.CapsuleGeometry(g.size[0],2*g.size[1],12,24);if(g.type!=='box')geometry.rotateX(Math.PI/2);
 const arm=g.body.includes('arm')||g.body.includes('hand'),color=arm?(g.body.startsWith('right')?0xe46a33:0xf0b23d):0x8b9aa9;
 const material=new T.MeshStandardMaterial({color,roughness:.8,depthTest:true,depthWrite:true,transparent:false});
 const mesh=new T.Mesh(geometry,material);mesh.userData.body=g.body_id;root.add(mesh);
 const line=new T.LineSegments(new T.EdgesGeometry(geometry,25),new T.LineBasicMaterial({color:0x448a94,depthTest:true,transparent:false}));reference.add(line);return mesh;
});
const handle=new T.Object3D();scene.add(handle);const gizmo=new TransformControls(camera,canvas);gizmo.setSize(.8);gizmo.setMode('rotate');gizmo.setSpace('world');scene.add(gizmo);gizmo.attach(handle);
let syncingHandle=false;const raycaster=new T.Raycaster(),mouse=new T.Vector2();
function applyMeshes(target,f){const pose=fk(m,f);target.children.forEach((mesh,i)=>{const g=m.geometry[i];mesh.position.fromArray(g.local_p).applyQuaternion(pose.q[g.body_id]).add(pose.p[g.body_id]);mesh.quaternion.copy(pose.q[g.body_id]).multiply(new T.Quaternion().fromArray(g.local_q))});return pose}
applyMeshes(reference,m.base);
function render(){renderer.render(scene,camera)}
function resize(){const w=canvas.clientWidth,h=canvas.clientHeight;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();render()}
function canMove(body){return body===0||chains.some(c=>c[1]===body||c[2]===body)}
function syncHandle(){if(gizmo.dragging||syncingHandle)return;syncingHandle=true;const pose=fk(m,frame);handle.position.copy(pose.p[selected]);handle.quaternion.copy(pose.q[selected]);handle.updateMatrixWorld();syncingHandle=false}
function labelState(){
 $('#body').value=String(selected);$('#rotate').classList.toggle('active',mode==='rotate');$('#move').classList.toggle('active',mode==='translate');$('#move').disabled=!canMove(selected);
 $('#modehint').textContent=mode==='rotate'?(selected===0?'Rotate the pelvis; both legs compensate to keep the feet planted and their angles unchanged.':'Rotate at this joint; attached parts follow.'):(selected===0?'Move the whole pose.':chains.some(c=>c[1]===selected)?'Move the elbow/knee bend direction; keep the hand/foot in place.':'Move this hand/foot with IK. Bone lengths stay fixed.');
 $('#overlay').textContent=`${labels[selected]} · ${mode==='rotate'?'Rotate':'Move with IK'}${pelvisLimited?' · Rotation limited to keep feet planted':''}${changed?' · Unsaved changes':''}`;
 $('#undo').disabled=!undo.length;$('#redo').disabled=!redo.length;$('#load-saved').disabled=!saved;
 $('#move-buttons').querySelectorAll('button').forEach(b=>b.disabled=!canMove(selected));
}
function update(){applyMeshes(root,frame);meshes.forEach(mesh=>{mesh.material.emissive.setHex(mesh.userData.body===selected?0x124658:0x000000);mesh.material.emissiveIntensity=.6});syncHandle();labelState();render()}
function select(body){selected=body;pelvisLimited=false;if(mode==='translate'&&!canMove(body))mode='rotate';gizmo.setMode(mode);update()}
function setMode(value){if(value==='translate'&&!canMove(selected))return;mode=value;gizmo.setMode(mode);update()}
function push(){undo.push(frame.slice());if(undo.length>100)undo.shift();redo=[]}
function autosave(){localStorage.setItem(draftKey,JSON.stringify({frame,base_sha256:m.base_sha256,updated:new Date().toISOString()}));changed=isChanged()}
function pins(f){const pose=fk(m,f);return [5,8].map(i=>[i,pose.p[i].clone()])}
function applyPins(p){if(!$('#pin').checked||![0,1].includes(selected))return;for(const [end,target] of p)solveIK(m,frame,end,target,null,$('#limits').checked)}
function moveBody(body,target){if(body===0){frame.splice(0,3,...target.toArray());return 0}const c=chains.find(c=>c[1]===body||c[2]===body);if(c[1]===body)return solveIK(m,frame,c[2],fk(m,frame).p[c[2]],target,$('#limits').checked);return solveIK(m,frame,body,target,null,$('#limits').checked)}
function rotateBody(body,q,p){pelvisLimited=false;if(body===0){const result=rotatePelvisKeepingFeet(m,frame,q,$('#limits').checked);pelvisLimited=result.fraction<.99999}else setWorldRotation(m,frame,body,q,$('#limits').checked);if(p)applyPins(p)}
function complete(){autosave();dragBase=null;dragPins=null;syncHandle();update();scheduleValidation()}
gizmo.addEventListener('dragging-changed',e=>{orbit.enabled=!e.value;if(!e.value){syncHandle();render()}});
gizmo.addEventListener('mouseDown',()=>{push();dragBase=frame.slice();dragPins=pins(frame)});
gizmo.addEventListener('objectChange',()=>{
 if(syncingHandle||!dragBase)return;const p=handle.position.clone(),q=handle.quaternion.clone();frame=dragBase.slice();
 if(mode==='rotate')rotateBody(selected,q,dragPins);else {moveBody(selected,p);if(selected===0)applyPins(dragPins)}
 changed=true;update();
});
gizmo.addEventListener('mouseUp',()=>complete());gizmo.addEventListener('change',render);orbit.addEventListener('change',render);
let pointerStart=null,onGizmo=false;
canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;pointerStart=[e.clientX,e.clientY];onGizmo=Boolean(gizmo.axis)});
canvas.addEventListener('pointerup',e=>{if(!pointerStart)return;const delta=Math.hypot(e.clientX-pointerStart[0],e.clientY-pointerStart[1]);pointerStart=null;if(onGizmo||delta>4||gizmo.dragging)return;const rect=canvas.getBoundingClientRect();mouse.set((e.clientX-rect.left)/rect.width*2-1,1-(e.clientY-rect.top)/rect.height*2);raycaster.setFromCamera(mouse,camera);const hit=raycaster.intersectObjects(meshes)[0];if(hit)select(hit.object.userData.body)});
labels.forEach((name,i)=>$('#body').add(new Option(name,String(i))));$('#body').onchange=()=>select(+$('#body').value);$('#rotate').onclick=()=>setMode('rotate');$('#move').onclick=()=>setMode('translate');$('#space').onchange=()=>{gizmo.setSpace($('#space').value);render()};$('#reference').onchange=()=>{reference.visible=$('#reference').checked;render()};
function rotationStep(axis,degrees,forceTorso=false){push();if(forceTorso){selected=1;mode='rotate';gizmo.setMode(mode)}const p=pins(frame),pose=fk(m,frame),v=new T.Vector3().setComponent(axis,1);let q=new T.Quaternion().setFromAxisAngle(v,degrees*Math.PI/180);q=$('#space').value==='local'&&!forceTorso?pose.q[selected].clone().multiply(q):q.multiply(pose.q[selected]);rotateBody(selected,q,p);complete()}
function moveStep(axis,cm){if(!canMove(selected))return;push();const pose=fk(m,frame),v=new T.Vector3().setComponent(axis,cm/100);if($('#space').value==='local')v.applyQuaternion(pose.q[selected]);moveBody(selected,pose.p[selected].clone().add(v));complete()}
for(let axis=0;axis<3;axis++)for(const sign of [-1,1]){
 const r=document.createElement('button');r.textContent=`${'XYZ'[axis]} ${sign<0?'−':'+'}`;r.setAttribute('aria-label',`Rotate ${'XYZ'[axis]} ${sign<0?'minus':'plus'}`);r.onclick=()=>rotationStep(axis,sign*Number($('#angle-step').value));$('#rotate-buttons').append(r);
 const t=document.createElement('button');t.textContent=r.textContent;t.setAttribute('aria-label',`Move ${'XYZ'[axis]} ${sign<0?'minus':'plus'}`);t.onclick=()=>moveStep(axis,sign*Number($('#move-step').value));$('#move-buttons').append(t);
}
$('#lean-forward').onclick=()=>rotationStep(1,2,true);$('#lean-back').onclick=()=>rotationStep(1,-2,true);
function doUndo(){if(!undo.length)return;redo.push(frame.slice());frame=undo.pop();pelvisLimited=false;complete()}
function doRedo(){if(!redo.length)return;undo.push(frame.slice());frame=redo.pop();pelvisLimited=false;complete()}
$('#undo').onclick=doUndo;$('#redo').onclick=doRedo;$('#reset').onclick=()=>{push();frame=m.base.slice();complete()};
window.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?doRedo():doUndo()}else if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){e.preventDefault();doRedo()}else if(e.key.toLowerCase()==='w')setMode('translate');else if(e.key.toLowerCase()==='r')setMode('rotate')});
document.querySelectorAll('[data-camera]').forEach(b=>b.onclick=()=>{const views={three:[1.7,1.2,1],front:[1.8,0,.8],left:[.15,-1.7,.8],right:[.15,1.7,.8],back:[-1.5,0,.8]};camera.position.fromArray(views[b.dataset.camera]);orbit.target.set(.13,.025,.35);orbit.update();render()});
async function validate(){const version=++validationVersion;try{const res=await fetch('/api/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frame})});const a=await res.json();if(version!==validationVersion)return;if(!res.ok)throw Error(a.error);
 const pairs=a.collisions.filter(x=>x.a.includes('arm')||x.a.includes('hand')||x.b.includes('arm')||x.b.includes('hand'));
 $('#checks').textContent=`Arm/leg or trunk overlap: ${pairs.length?Math.max(...pairs.map(x=>x.depth_cm)).toFixed(2)+' cm':'none'}\nLowest collider: ${a.floor_min_cm.toFixed(2)} cm\nJoint range: ${a.joint_limits.length?a.joint_limits.map(x=>labels[m.names.indexOf(x)]).join(', ')+' outside range':'within range'}`;
 $('#checks').className=a.joint_limits.length||a.collisions.length?'warn':'ok';
 }catch(e){$('#checks').textContent=e.message}}
function scheduleValidation(){clearTimeout(validationTimer);validationTimer=setTimeout(validate,150)}$('#validate').onclick=validate;
function screenshot(){const was=gizmo.visible;gizmo.visible=false;render();const image=canvas.toDataURL('image/png');gizmo.visible=was;render();return image}
$('#capture').onclick=()=>{const a=document.createElement('a');a.href=screenshot();a.download='sitting-pose.png';a.click()};
$('#save').onclick=async()=>{try{$('#save').disabled=true;const result=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({frame,base_sha256:m.base_sha256,screenshot:screenshot()})});const a=await result.json();if(!result.ok)throw Error(a.error);saved={frame:frame.slice(),base_sha256:m.base_sha256};changed=false;$('#saved').textContent='Saved: '+a.current+' — training not changed.';labelState()}catch(e){$('#saved').textContent='Save failed: '+e.message}finally{$('#save').disabled=false}};
$('#load-saved').onclick=()=>{if(!saved)return;push();frame=saved.frame.slice();complete()};
if(saved)$('#saved').textContent='A previously saved pose is available. Use Load last saved pose to restore it.';
window.addEventListener('resize',resize);resize();update();validate();
// The editor is event-driven: no simulation or permanent render loop while idle.
