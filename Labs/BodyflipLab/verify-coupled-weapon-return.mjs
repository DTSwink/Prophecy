// Full browser-script order and app initialization using an in-memory DOM/GL sink.
// Real local data and the app's single Jolt world; no browser or live state writes.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js');globalThis.Recovery=R;
const {createPhysics}=await import('./physics.mjs');let worlds=0,physics;
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8'),ids=new Map(),gl=new Proxy({getShaderParameter:()=>true,getProgramParameter:()=>true,getAttribLocation:()=>0,getUniformLocation:()=>({})},{get:(t,k)=>t[k]??(k.toUpperCase()===k?1:()=>({}))});
class Element{constructor(tag='div'){this.tagName=tag.toUpperCase();this.value='';this.children=[];this.dataset={};this.style={setProperty(){}};this.attrs={};this.classList={add(){},remove(){},toggle(){},contains(){return false;}};this.parentElement={classList:this.classList,insertBefore(){}};this.textContent='';this.clientWidth=1280;this.clientHeight=720;}
 get childNodes(){return this.children;} append(...a){for(const x of a){x.parent=this;this.children.push(x);}}replaceChildren(...a){this.children=[];this.append(...a);}remove(){if(this.parent)this.parent.children=this.parent.children.filter(e=>e!==this);}setAttribute(k,v){this.attrs[k]=v;}getAttribute(k){return this.attrs[k];}addEventListener(){}getBoundingClientRect(){return {left:0,top:0,width:1280,height:720};}getContext(){return gl;}setPointerCapture(){}contains(e){return this===e||this.children.some(x=>x.contains(e));}closest(){return null;}matches(){return false;}focus(){}blur(){} }
Element.prototype.toggleAttribute=function(k,force){const present=force??!(k in this.attrs);if(present)this.attrs[k]='';else delete this.attrs[k];return present;};
for(const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g)){const e=new Element(m[1]);e.id=m[2];for(const a of m[0].matchAll(/([\w-]+)="([^"]*)"/g))e.attrs[a[1]]=a[2];e.value=e.attrs.value||'';e.type=e.attrs.type||'';ids.set(e.id,e);}
const footer=new Element(),document={body:new Element('body'),hidden:false,activeElement:null,getElementById:id=>ids.get(id)||null,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),addEventListener(){},querySelector:()=>footer,querySelectorAll:selector=>selector.includes('axisGrid')?ids.get('axisGrid').children:[]};
const fixture=JSON.parse(fs.readFileSync(new URL(process.argv[2]||'saved-profile.json',import.meta.url)));fixture.playback.playing=false;
const fetched=[],writes=[];let timers=0;
const ctx=vm.createContext({document,console,structuredClone,performance,URL,TextEncoder,TextDecoder,Float32Array,Float64Array,Int32Array,Uint8Array,ArrayBuffer,Buffer,Math,Date,Map,Set,WeakMap,WeakSet,atob,devicePixelRatio:1,ResizeObserver:class{observe(){}},Option:function(text,value){const e=new Element('option');e.textContent=text;e.value=value;return e;},setTimeout:()=>++timers,clearTimeout(){},requestAnimationFrame:()=>1,cancelAnimationFrame(){},location:{reload(){}},crypto:{randomUUID:()=> 'test'},fetch:async(path,options)=>{fetched.push(path);if(options?.method==='POST'){writes.push(path);return {ok:true,json:async()=>({})};}if(path==='/state')return {ok:true,json:async()=>structuredClone(fixture)};const bytes=fs.readFileSync(new URL(path,import.meta.url));return {ok:true,json:async()=>JSON.parse(bytes),arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};},__createPhysics:async(...a)=>{worlds++;physics=await createPhysics(...a);return physics;}});ctx.window=ctx;ctx.addEventListener=()=>{};
const scripts=[...html.matchAll(/<script src="([^"]+)"/g)].map(m=>m[1]);
ctx.setTimeout=(callback,delay=0)=>{if(delay===0)queueMicrotask(callback);return ++timers;};
try{
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(process.argv[3]==='baseline'&&['core.js','jump-attack.js'].includes(file)?'../../Saved/BodyflipLab/trimmed-sword-before-'+file:file,import.meta.url),'utf8');if(file==='physical-aim.js')code=code.replace('return {sample,prepare,statistics,','return {sample,prepare,statistics,neutralSample:neutral.sample,').replace('const statistics={evaluations:0}', 'root.__aimInputs ||= []; root.__aimInputs.push({rawSource:originalSource,physicalOptions,track,clip,settings,project,worldPose});const statistics={evaluations:0}');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}

 await vm.runInContext('init()',ctx);



 const results=[];
 for(const spec of [{attack:'slashLU',cut:20,weight:.4},{attack:'slashLU',cut:21,weight:.4},{attack:'slashLU',cut:20,weight:0},{attack:'slashL',cut:23,weight:.4}]){
  ctx.spec=spec;await vm.runInContext(`(async()=>{settings=C.sanitize({...settings,mode:'spaceGym',airFlip:false,spaceFallAnimation:true,attackReturnDistance:spec.weight,attackEndFrames:{[spec.attack]:spec.cut},jumpEvents:[{...settings.jumpEvents[0],enabled:true,attack:spec.attack,flip:0,twist:0}]});await prepareRun({preserveTime:true});})()`,ctx);
  const report=vm.runInContext(`(()=>{
   const tr=flight.segments[0].attack,hand=names.indexOf('hand_r'),forearm=parents[hand],wrist=BodyflipWrist.create(idle,forearm,hand,'R'),render=Object.create(WebGLMotionRenderer.prototype),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
   const vertices=Array.from({length:swordMesh.vertices.length/3},(_,i)=>Array.from(swordMesh.vertices.slice(i*3,i*3+3))),zs=[Math.min(...vertices.map(v=>v[2])),Math.max(...vertices.map(v=>v[2]))],origin=render.swordLocalToWorld([0,0,0],[0,0,0],[[1,0,0],[0,1,0],[0,0,1]]),radius=Math.max(...vertices.map(v=>R.length(R.sub(render.swordLocalToWorld([v[0],v[1],0],[0,0,0],[[1,0,0],[0,1,0],[0,0,1]]),origin))));
   const sample=t=>physics.target(aimTimelinePoseAt(t));let peakWrist=0,travel=0,minClearance=Infinity,prev=sample(tr.end);
   for(let i=0;i<=240;i++){const p=sample(tr.end+(tr.returnEnd-tr.end)*i/240),head=render.headFrame(p),axis=zs.map(z=>R.add(p.points[hand],R.rotate(p.q[hand],C.swordPoint(swordMesh,z))));peakWrist=Math.max(peakWrist,angle(wrist.clamp(p.q[forearm],p.q[hand]),p.q[hand]));if(i)travel+=angle(p.q[hand],prev.q[hand]);prev=p;minClearance=Math.min(minClearance,Math.min(...Array.from({length:21},(_,k)=>C.segmentDistance(R.add(head.lower,R.mul(R.sub(head.upper,head.lower),k/20)),...axis)))-head.radius-radius-head.segmentLength/40);}
   const h=1e-7,joins=[tr.end,tr.returnEnd].map(t=>{const a=tr.sample(t-h).pose,b=tr.sample(t).pose,c=tr.sample(t+h).pose;return {jump:angle(a.q[hand],c.q[hand]),handVelocityJump:R.length(R.sub(R.mul(R.qlog(R.qm(c.q[hand],R.qinv(b.q[hand]))),1/h),R.mul(R.qlog(R.qm(b.q[hand],R.qinv(a.q[hand]))),1/h))),wristSpeedJump:R.length(R.sub(R.mul(R.sub(c.points[hand],b.points[hand]),1/h),R.mul(R.sub(b.points[hand],a.points[hand]),1/h)))};});
   const mid=(tr.end+tr.returnEnd)/2,frozen=JSON.stringify(sample(mid));sample(tr.start);sample(tr.returnEnd+1);
   return {...spec,peakWristDegrees:peakWrist*180/Math.PI,travelDegrees:travel*180/Math.PI,minClearance,joins,deterministic:frozen===JSON.stringify(sample(mid))};
  })()`,ctx);
  assert(report.minClearance>0,'sword mesh clears rendered head');
  assert(report.joins.every(j=>j.jump<3e-5&&j.handVelocityJump<.01&&j.wristSpeedJump<.002),'continuous hand motion at cut and return end');
  assert(report.deterministic,'deterministic seek');
  assert(report.travelDegrees<360,'no extra full sword turn');
  // Attacks may exceed resting limits: preserve that contract, but catch the
  // 128-degree wrist reversal of this fixture and the Slash L regression.
  assert(report.peakWristDegrees<(spec.attack==='slashLU'&&spec.cut===20&&spec.weight>0?8:1e-6),'no broken-wrist return');
  console.log(JSON.stringify(report));results.push(report);
 }

 const coupling=vm.runInContext(`(()=>{
  const names=['root','upperarm_r','lowerarm_r','hand_r'],parents=[-1,0,1,2],p=[[0,0,0],[0,0,0],[1,0,0],[1,0,0]],rest=R.fk({p,q:names.map(()=>[0,0,0,1])},parents),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));C.registerRig(names,parents,rest);
  let netError=0,unchangedError=0;
  for(const [f,w] of [[80,-79],[80,5],[1,0]]){
   const outgoing=t=>R.fk({p,q:[[0,0,0,1],[0,0,0,1],R.qexp([f*t,0,0]),R.qexp([w*t,0,0])]},parents),ordinary=C.transition(outgoing,()=>rest,.3,parents,null,true),coupled=C.transition(outgoing,()=>rest,.3,parents,null,true,false,3);
   for(let i=0;i<=100;i++){const a=ordinary(.3*i/100),b=coupled(.3*i/100);netError=Math.max(netError,angle(a.q[3],b.q[3]));if(w>=0)unchangedError=Math.max(unchangedError,...a.q.map((q,j)=>angle(q,b.q[j])));}
  }
  return {netError,unchangedError};
 })()`,ctx);assert(coupling.netError<1e-9&&coupling.unchangedError<1e-12,'same net hand inertia and no change to non-cancelling motion');
 console.log(JSON.stringify({passed:true,cases:results.length,coupling,liveWrites:0}));

}finally{physics?.dispose();}
