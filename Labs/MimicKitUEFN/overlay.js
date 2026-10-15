import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';

const $=id=>document.getElementById(id), canvas=$('canvas');
const scene=new THREE.Scene();scene.background=new THREE.Color('#10151d');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));
const camera=new THREE.PerspectiveCamera(38,1,.01,100);camera.up.set(0,0,1);
const orbit=new OrbitControls(camera,canvas);orbit.target.set(0,0,.9);orbit.enableDamping=false;
scene.add(new THREE.HemisphereLight(0xffffff,0x556078,2.3));
const light=new THREE.DirectionalLight(0xffffff,2.5);light.position.set(3,-4,5);scene.add(light);
const grid=new THREE.GridHelper(5,50,0x46556a,0x253342);grid.rotation.x=Math.PI/2;scene.add(grid);
const groups={phat:new THREE.Group(),new:new THREE.Group(),old:new THREE.Group()};
Object.values(groups).forEach(g=>scene.add(g));
const skeletons={phat:new THREE.Group(),new:new THREE.Group()};
Object.entries(skeletons).forEach(([name,g])=>groups[name].add(g));
let data, selected='', meshes={}, deltas={}, liveFrames={};
const identity=()=>new THREE.Quaternion();
const matrix=t=>new THREE.Matrix4().compose(new THREE.Vector3(...t.position),new THREE.Quaternion(...t.quaternion),new THREE.Vector3(1,1,1));
const colour={phat:0x39dfdd,new:0xf59c44,old:0xc3c9d5};

function shape(g,layer){
 let geom;
 if(g.type==='box')geom=new THREE.BoxGeometry(...g.size.map(v=>v*2));
 else if(g.type==='sphere')geom=new THREE.SphereGeometry(g.size[0],layer==='phat'?12:20,layer==='phat'?6:12);
 else {geom=new THREE.CapsuleGeometry(g.size[0],2*g.size[1],layer==='phat'?4:8,layer==='phat'?10:20);geom.rotateX(Math.PI/2);}
 const mat=layer==='phat'?new THREE.LineBasicMaterial({color:colour.phat,transparent:true,opacity:.38,depthTest:false}):
 new THREE.MeshStandardMaterial({color:colour[layer],roughness:.7,transparent:true,opacity:layer==='new'?.6:.25,depthWrite:false});
 const obj=layer==='phat'?new THREE.LineSegments(new THREE.WireframeGeometry(geom),mat):new THREE.Mesh(geom,mat);
 obj.matrixAutoUpdate=false;obj.matrix.copy(matrix(g));obj.userData=g;
 if(layer==='phat')obj.renderOrder=2;
 groups[layer].add(obj);return obj;
}

function drawSkeleton(layer,frames,parents){
 const target=skeletons[layer];
 while(target.children.length){const o=target.children[0];o.geometry?.dispose();o.material?.dispose();target.remove(o);}
 const points=[];
 for(const [child,parent]of Object.entries(parents)){
  const a=frames[child],b=frames[parent];if(!a||!b)continue;
  points.push(new THREE.Vector3().setFromMatrixPosition(a),new THREE.Vector3().setFromMatrixPosition(b));
 }
 const line=new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:colour[layer],depthTest:false}));line.renderOrder=3;target.add(line);
 for(const m of Object.values(frames)){
  const dot=new THREE.Mesh(new THREE.SphereGeometry(.007,8,6),new THREE.MeshBasicMaterial({color:colour[layer],depthTest:false}));
  dot.position.setFromMatrixPosition(m);dot.renderOrder=4;target.add(dot);
 }
}

function updatePose(){
 const rest=data.meta.body_frames,parents=data.meta.parents;liveFrames={};
 function get(name){
  if(liveFrames[name])return liveFrames[name];
  const parent=parents[name], base=matrix(rest[name]);
  const local=parent?matrix(rest[parent]).invert().multiply(base):base;
  local.multiply(new THREE.Matrix4().makeRotationFromQuaternion(deltas[name]??identity()));
  liveFrames[name]=parent?get(parent).clone().multiply(local):local;return liveFrames[name];
 }
 for(const n of Object.keys(rest))get(n);
 for(const mesh of meshes.new){const g=mesh.userData;mesh.matrix.copy(liveFrames[g.body]).multiply(matrix(rest[g.body]).invert()).multiply(matrix(g));}
 drawSkeleton('new',liveFrames,parents);
 updateView();
}

function updateView(){
 if(!data)return;
 for(const layer of ['phat','new','old'])groups[layer].visible=$('show'+layer[0].toUpperCase()+layer.slice(1)).checked;
 const shift=+$('offset').value;groups.new.position.y=-shift;groups.old.position.y=shift;
 $('offsetValue').textContent=Math.round(shift*100)+' cm';
 const alpha=+$('opacity').value;$('opacityValue').textContent=Math.round(alpha*100)+'%';
 for(const [layer,objects]of Object.entries(meshes))for(const mesh of objects){
  const belongs=!selected||mesh.userData.body===selected;
  mesh.visible=!$('isolate').checked||belongs;
  if(layer==='new'){mesh.material.opacity=alpha;mesh.material.color.setHex(selected&&belongs?0xffd85e:colour.new);}
 }
 for(const s of Object.values(skeletons))s.visible=$('bones').checked&&!$('isolate').checked;
 renderer.render(scene,camera);
}

function referenceQ(j){const [w,x,y,z]=j.reference_wxyz;return new THREE.Quaternion(x,y,z,w);}
function coordinates(q){const {w,x,y,z}=q,n=Math.hypot(w,x);let tw=2*Math.atan2(x,w);if(tw>Math.PI)tw-=2*Math.PI;if(tw< -Math.PI)tw+=2*Math.PI;return[tw,2*Math.asin(THREE.MathUtils.clamp((w*y-x*z)/n,-1,1)),2*Math.asin(THREE.MathUtils.clamp((x*y+w*z)/n,-1,1))];}
function selectBody(){
 selected=$('body').value;const control=$('angleControls');control.replaceChildren();
 const group=data.meta.groups[selected],j=data.meta.joints.find(j=>j.body===selected);
 $('detail').textContent=group?`${group.colliders_from.join(', ')}\n${j?'Joint limits: '+j.source_body:'Fixed within parent; no additional joint.'}`:'';
 control.hidden=!j;$('jointReset').hidden=!j;
 if(j){
  const q=referenceQ(j).multiply(deltas[selected]??identity()),vals=coordinates(q).map(THREE.MathUtils.radToDeg);
  const limits=j.limits_rad.map(v=>Number(THREE.MathUtils.radToDeg(v).toFixed(6)));
  for(let i=0;i<3;i++){
   const label=document.createElement('label'),span=document.createElement('span'),readout=document.createElement('span');
   span.textContent=['Twist','Swing 2','Swing 1'][i];readout.id='angleValue'+i;readout.textContent=vals[i].toFixed(1)+'°';label.append(span,readout);control.append(label);
   const slider=document.createElement('input');slider.type='range';slider.id='angle'+i;slider.min=-limits[i];slider.max=limits[i];slider.step='.1';slider.value=vals[i];slider.disabled=j.modes[i]===2;slider.setAttribute('aria-label',span.textContent);slider.addEventListener('input',()=>applyAngles(j));control.append(slider);
  }
 }
 updateView();
}
function applyAngles(j){
 let values=[0,1,2].map(i=>j.modes[i]===2?0:THREE.MathUtils.degToRad(+$('angle'+i).value));
 let sy=Math.sin(values[1]/2),sz=Math.sin(values[2]/2);
 if(j.modes[1]===1&&j.modes[2]===1){const radius=Math.hypot(sy/Math.sin(j.limits_rad[1]/2),sz/Math.sin(j.limits_rad[2]/2));if(radius>1){sy/=radius;sz/=radius;}}
 const swing=new THREE.Quaternion(0,sy,sz,Math.sqrt(Math.max(0,1-sy*sy-sz*sz)));
 const twist=new THREE.Quaternion(Math.sin(values[0]/2),0,0,Math.cos(values[0]/2));
 const full=swing.multiply(twist);deltas[selected]=referenceQ(j).invert().multiply(full);
 values=coordinates(full).map(THREE.MathUtils.radToDeg);
 for(let i=0;i<3;i++){$('angle'+i).value=values[i];$('angleValue'+i).textContent=values[i].toFixed(1)+'°';}
 updatePose();
}
function view(which){const positions={front:[3,0,1],side:[0,-3,1],perspective:[2.3,-2.3,1.7]};camera.position.set(...positions[which]);orbit.target.set(0,0,.9);orbit.update();updateView();}
function resize(){const r=$('view').getBoundingClientRect();renderer.setSize(r.width,r.height,false);camera.aspect=r.width/r.height;camera.updateProjectionMatrix();updateView();}
new ResizeObserver(resize).observe($('view'));orbit.addEventListener('change',updateView);
for(const id of ['showPhat','showNew','showOld','bones','isolate','opacity','offset'])$(id).addEventListener('input',updateView);
for(const name of ['front','side','perspective'])$(name).onclick=()=>view(name);
$('body').onchange=selectBody;$('jointReset').onclick=()=>{delete deltas[selected];updatePose();selectBody();};
$('rest').onclick=()=>{deltas={};updatePose();selectBody();};
try{
 const response=await fetch('./overlay-data.json');if(!response.ok)throw Error('Geometry data unavailable');data=await response.json();
 for(const layer of ['phat','new','old'])meshes[layer]=data[layer].map(g=>shape(g,layer));
 for(const name of Object.keys(data.meta.groups)){const option=document.createElement('option');option.value=name;option.textContent=name.replaceAll('_',' ');$('body').append(option);}
 drawSkeleton('phat',Object.fromEntries(Object.entries(data.meta.source_body_frames).map(([k,v])=>[k,matrix(v)])),data.meta.source_parents);
 $('status').textContent=`Rest-pose collider error: ${(data.meta.geom_surface_max_error_m*100).toExponential(2)} cm\nMass: ${data.meta.mass_kg.toFixed(3)} kg\nOriginal model is read-only. Training is unchanged.`;
 $('status').style.whiteSpace='pre-line';updatePose();view('perspective');resize();
 window.overlayDebug={data,get liveFrames(){return liveFrames;},get deltas(){return deltas;},meshes,groups};
}catch(e){$('error').hidden=false;$('error').textContent=e.stack;throw e;}
