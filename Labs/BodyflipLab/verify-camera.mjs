import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./camera.js'),R=require('./recovery.js');
const checks=[],check=(name,value)=>{assert(value,name);checks.push(name);},near=(a,b)=>R.length(R.sub(a,b))<1e-9;
const defaults={yaw:-.55,pitch:-.06,zoom:.95,panX:0,panY:0,free:false,offset:null,freeView:null};
const center=[3,2,-8];let maxSwitchError=0,maxRecenterError=0;
for(const pitch of [-5,-.06,1.75])for(const zoom of [.001,.95,3]){
 const state={...defaults,pitch,zoom,panX:137,panY:-71},before=K.view(state,center,800);
 K.toggle(state,true,before,center);const free=K.view(state,[50,100,200],800);
 K.toggle(state,false,free,center);const after=K.view(state,center,800);
 maxSwitchError=Math.max(maxSwitchError,R.length(R.sub(before.eye,free.eye)),R.length(R.sub(before.target,free.target)));
 maxRecenterError=Math.max(maxRecenterError,R.length(R.sub(after.target,center)),R.length(R.sub(after.forward,free.forward)),Math.abs(after.targetDepth-free.targetDepth));
}
check('Entering free camera preserves eye and target, including panned/top/distant views',maxSwitchError<1e-9);
check('Leaving free camera centers COM and preserves angle and viewing distance',maxRecenterError<1e-9);
const orbit={...defaults,panX:20,panY:10},orbitBefore=K.view(orbit,center,800);
K.rotate(orbit,50,1000);const overhead=K.view(orbit,center,800);
check('Orbit can look down almost vertically',overhead.forward[1]<-.99999);
check('Orbit holds distance and focal point',Math.abs(overhead.targetDepth-orbitBefore.targetDepth)<1e-9);
check('Horizontal orbit retains requested direction',Math.abs(orbit.yaw-defaults.yaw+50*.008)<1e-10);
const radius=overhead.targetDepth;K.wheel(orbit,-100);
check('Wheel can still zoom in from overhead',K.view(orbit,center,800).targetDepth<radius);
K.rotate(orbit,0,-2000);check('Orbit can also look upward almost vertically',K.view(orbit,center,800).forward[1]>.99999);
const savedOrbit={};K.restore(savedOrbit,JSON.parse(JSON.stringify(orbit)),defaults);
check('Extended orbit survives saved camera restore',near(K.view(savedOrbit,center,800).eye,K.view(orbit,center,800).eye));
const state={...defaults},initial=K.view(state,center,800);K.toggle(state,true,initial,center);
const eye=state.freeView.eye.slice();K.rotate(state,50,20);const turned=K.view(state,center,800);
check('Free left-drag turns in place',near(turned.eye,eye)&&!near(turned.forward,initial.forward));
check('Requested inverted vertical drag is retained',turned.forward[1]<initial.forward[1]);
check('Free camera ignores moving COM',near(K.view(state,[100,20,-80],800).eye,turned.eye));
const left=structuredClone(state),forward=structuredClone(state),right=structuredClone(state),back=structuredClone(state);
K.move(left,new Set(['q']),1);K.move(forward,new Set(['z']),1);K.move(right,new Set(['d']),1);K.move(back,new Set(['s']),1);
check('Q/D strafe camera left/right',near(R.sub(right.freeView.eye,eye),R.mul(turned.right,3))&&near(R.sub(left.freeView.eye,eye),R.mul(turned.right,-3)));
check('Z/S move along view direction',near(R.sub(forward.freeView.eye,eye),R.mul(turned.forward,3))&&near(R.sub(back.freeView.eye,eye),R.mul(turned.forward,-3)));
const diagonal=structuredClone(state);K.move(diagonal,new Set(['z','d']),1);check('Diagonal movement does not speed up',Math.abs(R.length(R.sub(diagonal.freeView.eye,eye))-3)<1e-9);
const target=turned.target.slice(),distance=state.freeView.distance;K.wheel(state,100);
check('Wheel retains exponential zoom and current focal point',Math.abs(state.freeView.distance-distance*Math.exp(.1))<1e-9&&near(K.view(state,center,800).target,target));
K.wheel(state,15000);check('Wheel retains unlimited dezoom',state.zoom<1e-5);
const restored={};K.restore(restored,JSON.parse(JSON.stringify(state)),defaults);
check('Saved free camera restores the same view',near(K.view(restored,center,800).eye,K.view(state,center,800).eye));
K.toggle(state,false,K.view(state,center,800),center);const following=K.view(state,center,800);
check('Follow resumes centered after free movement and zoom',near(following.target,center)&&near(R.sub(K.view(state,R.add(center,[2,0,0]),800).eye,following.eye),[2,0,0]));

const app=fs.readFileSync(new URL('app.js',import.meta.url),'utf8');let queued=0,cancelled=0;
// A fixed point on the pelvis must stay fixed on screen during any whole-body
// rotation/translation, while articulation relative to it must remain visible.
const cameraCoordinates=(v,p)=>{const d=R.sub(p,v.eye);return [R.dot(d,v.right),R.dot(d,v.up),R.dot(d,v.forward)];};
let maxPelvisError=0;
for(const free of [false,true]){
 const state={...defaults,panX:137,panY:-71},frame={point:[2,3,4],q:R.qexp([.4,-.8,1.2])};
 if(free)K.toggle(state,true,K.view(state,center,800),center);
 const previous=structuredClone(state),before=K.view(state,center,800),snapshot=JSON.stringify(frame);
 K.togglePelvis(state,true,before,frame);
 const attached=K.view(state,center,800,frame);
 check('Pelvis view preserves the current '+(free?'free':'follow')+' view',near(attached.eye,before.eye)&&near(attached.target,before.target)&&near(attached.up,before.up));
 for(const controls of [false,true]){
  if(controls){K.rotate(state,40,-80);K.pan(state,K.view(state,center,800,frame),70,35);K.wheel(state,150);}
  const view=K.view(state,center,800,frame),local=[.3,.8,-.2],point=R.add(frame.point,R.rotate(frame.q,local)),expected=cameraCoordinates(view,point);
  for(const axis of [[1,0,0],[0,1,0],[0,0,1],R.unit([1,2,-3])])for(const angle of [-Math.PI,Math.PI/2,Math.PI,Math.PI*1.5,Math.PI*2]){
   const q=R.qexp(R.mul(axis,angle)),next={point:R.add(frame.point,[5,-8,11]),q:R.qm(q,frame.q)},v=K.view(state,center,800,next),p=R.add(next.point,R.rotate(next.q,local));
   maxPelvisError=Math.max(maxPelvisError,R.length(R.sub(cameraCoordinates(v,p),expected)));
  }
  check('Pelvis-relative articulation remains visible',!near(cameraCoordinates(view,R.add(point,R.rotate(frame.q,[.1,0,0]))),expected));
 }
 const saved={};K.restore(saved,JSON.parse(JSON.stringify(state)),defaults);
 const a=K.view(saved,center,800,frame),b=K.view(state,center,800,frame);
 check('Saved pelvis camera restores eye and full rolled basis',near(a.eye,b.eye)&&near(a.up,b.up)&&near(a.right,b.right));
 K.togglePelvis(saved,false);check('Leaving pelvis view restores the previous camera',JSON.stringify({...saved,pelvisView:null})===JSON.stringify({...previous,pelvisView:null}));
 check('Pelvis view never changes the displayed pose',snapshot===JSON.stringify(frame));
}
check('Pelvis view cancels all rigid rotation and translation, including inverted and rolled frames',maxPelvisError<1e-9);
const renderContext={cameraState:{pelvisView:{}},WebGLMotionRenderer:class{draw(data){this.body=data;}}};vm.createContext(renderContext);
vm.runInContext(app.slice(app.indexOf('class BodyflipRenderer'),app.indexOf('function syncPlaybackReadout'))+';globalThis.TestRenderer=BodyflipRenderer;',renderContext);
const isolatedRenderer=new renderContext.TestRenderer(),displayed={points:[]};isolatedRenderer.draw(displayed,[0,0,0]);
check('Pelvis view draws the actual body and skips all scene/debug overlay work',isolatedRenderer.body===displayed);
const ctx={cameraState:{free:true},requestAnimationFrame:()=>++queued,cancelAnimationFrame:()=>cancelled++,save(){},document:{hidden:false},BodyflipCamera:K,playing:false,drawAll(){}};
vm.createContext(ctx);vm.runInContext(app.slice(app.indexOf('const cameraKeys='),app.indexOf('class BodyflipRenderer')),ctx);
const event=(key,target={},extra={})=>({key,target,preventDefault(){},stopImmediatePropagation(){},...extra});
check('QZDS works from a previously clicked checkbox',ctx.cameraKey(event('z',{tagName:'INPUT',type:'checkbox'}),true)&&queued===1);
ctx.cameraKey(event('z'),false);check('Releasing keys stops the camera RAF',cancelled===1);
check('Writing and Ctrl+Z keep their normal keys',!ctx.cameraKey(event('z',{tagName:'INPUT',type:'number'}),true)&&!ctx.cameraKey(event('z',{}, {ctrlKey:true}),true));
ctx.cameraState.free=false;check('QZDS is inactive in follow mode',!ctx.cameraKey(event('q'),true));
fs.writeFileSync(new URL('camera-verification.json',import.meta.url),JSON.stringify({passed:checks.length,checks,maxSwitchError,maxRecenterError,maxPelvisError,visualVerified:false},null,2)+'\n');
console.log(JSON.stringify({passed:checks.length,maxSwitchError,maxRecenterError,maxPelvisError}));
