// Full browser-script order and app initialization using an in-memory DOM/GL sink.
// Real local data and the app's single Jolt world; no browser or live state writes.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const variant='after',fixtureName=process.argv[2]||'fixtures/pike-spine-wrap.json',order=process.argv[3]||'forward';
const require=createRequire(import.meta.url),R=require('./recovery.js');globalThis.Recovery=R;
const {createPhysics}=await import('./physics.mjs');let worlds=0,physics;
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8'),ids=new Map(),gl=new Proxy({getShaderParameter:()=>true,getProgramParameter:()=>true,getAttribLocation:()=>0,getUniformLocation:()=>({})},{get:(t,k)=>t[k]??(k.toUpperCase()===k?1:()=>({}))});
class Element{constructor(tag='div'){this.tagName=tag.toUpperCase();this.value='';this.children=[];this.dataset={};this.style={setProperty(){}};this.attrs={};this.classList={add(){},remove(){},toggle(){},contains(){return false;}};this.parentElement={classList:this.classList,insertBefore(){}};this.textContent='';this.clientWidth=1280;this.clientHeight=720;}
 get childNodes(){return this.children;} append(...a){for(const x of a){x.parent=this;this.children.push(x);}}replaceChildren(...a){this.children=[];this.append(...a);}remove(){if(this.parent)this.parent.children=this.parent.children.filter(e=>e!==this);}setAttribute(k,v){this.attrs[k]=v;}getAttribute(k){return this.attrs[k];}addEventListener(){}getBoundingClientRect(){return {left:0,top:0,width:1280,height:720};}getContext(){return gl;}setPointerCapture(){}contains(e){return this===e||this.children.some(x=>x.contains(e));}closest(){return null;}matches(){return false;}focus(){}blur(){} }
Element.prototype.toggleAttribute=function(k,force){const present=force??!(k in this.attrs);if(present)this.attrs[k]='';else delete this.attrs[k];return present;};
for(const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g)){const e=new Element(m[1]);e.id=m[2];for(const a of m[0].matchAll(/([\w-]+)="([^"]*)"/g))e.attrs[a[1]]=a[2];e.value=e.attrs.value||'';e.type=e.attrs.type||'';ids.set(e.id,e);}
const footer=new Element(),document={body:new Element('body'),hidden:false,activeElement:null,getElementById:id=>ids.get(id)||null,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),addEventListener(){},querySelector:()=>footer,querySelectorAll:selector=>selector.includes('axisGrid')?ids.get('axisGrid').children:[]};
const fixture=JSON.parse(fs.readFileSync(new URL(fixtureName,import.meta.url)));fixture.playback.playing=false;
const fetched=[],writes=[];let timers=0;
const ctx=vm.createContext({document,console,structuredClone,performance,URL,TextEncoder,TextDecoder,Float32Array,Float64Array,Int32Array,Uint8Array,ArrayBuffer,Buffer,Math,Date,Map,Set,WeakMap,WeakSet,atob,devicePixelRatio:1,ResizeObserver:class{observe(){}},Option:function(text,value){const e=new Element('option');e.textContent=text;e.value=value;return e;},setTimeout:()=>++timers,clearTimeout(){},requestAnimationFrame:()=>1,cancelAnimationFrame(){},location:{reload(){}},crypto:{randomUUID:()=> 'test'},fetch:async(path,options)=>{fetched.push(path);if(options?.method==='POST'){writes.push(path);return {ok:true,json:async()=>({})};}if(path==='/state')return {ok:true,json:async()=>structuredClone(fixture)};const bytes=fs.readFileSync(new URL(path,import.meta.url));return {ok:true,json:async()=>JSON.parse(bytes),arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};},__createPhysics:async(...a)=>{worlds++;physics=await createPhysics(...a);return physics;}});ctx.window=ctx;ctx.addEventListener=()=>{};
const scripts=[...html.matchAll(/<script src="([^"]+)"/g)].map(m=>m[1]);
ctx.setTimeout=(callback,delay=0)=>{if(delay===0)queueMicrotask(callback);return ++timers;};
try{
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(file,import.meta.url),'utf8');if(file==='physical-aim.js')code=code.replace('const statistics={evaluations:0}', 'root.__aimInputs ||= []; root.__aimInputs.push({rawSource:originalSource});const statistics={evaluations:0}');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}

 await vm.runInContext('init()',ctx);



 ctx.order=order;
 const report=vm.runInContext(`(()=>{
  const seg=flight.segments.find(s=>s.attack),tr=seg.attack,angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI;
  const dt=1/960,start=tr.start-.01,end=tr.returnEnd+.05,times=Array.from({length:Math.ceil((end-start)/dt)+1},(_,i)=>start+i*dt),input=__aimInputs[0];
  const sample=t=>physics.target(aimTimelinePoseAt(t)),frames=new Map();
  const indices=names.map((_,i)=>i).slice(1),armIndices=names.map((n,i)=>/^(clavicle|upperarm|lowerarm|hand)_/.test(n)?i:-1).filter(i=>i>=0);
  const requested=order==='reverse'?times.slice().reverse():order==='shuffled'?times.slice().sort((a,b)=>Math.sin(a*12345)-Math.sin(b*12345)):times;
  for(const t of requested)frames.set(t,sample(t));
  let peak={degrees:0},armError=0,momentumError=0,previous=null,maxSpineStep=0;
  const captured=[];
  for(const t of times){const p=frames.get(t),local=R.localize(p.points,p.q,parents),raw=input.rawSource(t).pose,base=R.localize(raw.points,raw.q,parents);for(const i of armIndices)armError=Math.max(armError,angle(local.q[i],base.q[i]));
   if(previous)for(const i of indices){const a=angle(p.q[i],previous.q[i]);if(a>peak.degrees)peak={degrees:a,time:t,bone:names[i]};if(names[i].startsWith('spine_'))maxSpineStep=Math.max(maxSpineStep,a);}
   previous=p;momentumError=Math.max(momentumError,flight.sample(t).physical?.error||0);captured.push({time:t,pose:p});
  }
  let seekError=0;for(const t of times.slice().reverse()){const p=sample(t),q=frames.get(t);for(const i of indices)seekError=Math.max(seekError,angle(p.q[i],q.q[i]),R.length(R.sub(p.points[i],q.points[i])));}
  const joins=[tr.start,tr.start+tr.duration,tr.end,tr.returnEnd,1.8125].map(t=>({time:t,scales:[1e-4,5e-5,2.5e-5].map(h=>{const a=sample(t-h),b=sample(t+h);return {h,angle:Math.max(...indices.map(i=>angle(a.q[i],b.q[i]))),position:Math.max(...indices.map(i=>R.length(R.sub(a.points[i],b.points[i]))))};})}));
  return {peak,maxSpineStep,armError,momentumError,seekError,joins,timing:{start:tr.start,armed:tr.start+tr.duration,end:tr.end,returnEnd:tr.returnEnd},aimError:seg.physical.track.statistics.error,frames:captured};
 })()`,ctx);
console.log(JSON.stringify({variant,fixtureName,order,...report,frames:undefined},null,2));
 if(variant==='after'){assert(report.peak.degrees<5,'No frame snap at960Hz');assert(report.seekError<1e-7,'Deterministic reverse seeks');assert(report.armError<1e-7,'Arm-local animation unchanged');assert(report.momentumError<1e-4,'Momentum balance retained');assert(report.aimError<1e-5,'Target direction retained');}
}finally{physics?.dispose();}
