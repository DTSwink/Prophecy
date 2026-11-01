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
const fixture=JSON.parse(fs.readFileSync(new URL('fixtures/twist-attack.json',import.meta.url))).scene;fixture.playback.playing=false;
const fetched=[],writes=[];let timers=0;
const ctx=vm.createContext({document,console,structuredClone,performance,URL,TextEncoder,TextDecoder,Float32Array,Float64Array,Int32Array,Uint8Array,ArrayBuffer,Buffer,Math,Date,Map,Set,WeakMap,WeakSet,atob,devicePixelRatio:1,ResizeObserver:class{observe(){}},Option:function(text,value){const e=new Element('option');e.textContent=text;e.value=value;return e;},setTimeout:()=>++timers,clearTimeout(){},requestAnimationFrame:()=>1,cancelAnimationFrame(){},location:{reload(){}},crypto:{randomUUID:()=> 'test'},fetch:async(path,options)=>{fetched.push(path);if(options?.method==='POST'){writes.push(path);return {ok:true,json:async()=>({})};}if(path==='/state')return {ok:true,json:async()=>structuredClone(fixture)};const bytes=fs.readFileSync(new URL(path,import.meta.url));return {ok:true,json:async()=>JSON.parse(bytes),arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};},__createPhysics:async(...a)=>{worlds++;physics=await createPhysics(...a);return physics;}});ctx.window=ctx;ctx.addEventListener=()=>{};
const scripts=[...html.matchAll(/<script src="([^"]+)"/g)].map(m=>m[1]);
ctx.setTimeout=(callback,delay=0)=>{if(delay===0)queueMicrotask(callback);return ++timers;};
try{
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(file,import.meta.url),'utf8');if(file==='physical-aim.js')code=code.replace('const statistics={evaluations:0}', 'root.__aimInputs ||= []; root.__aimInputs.push({rawSource:originalSource,physicalOptions,track,clip,settings,project,worldPose});const statistics={evaluations:0}');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}

 await vm.runInContext('init()',ctx);const report=[];
 for(const [attack,aim,twist,momentum3D] of [['none',false,200,true],['slashL',false,200,true],['slashL',true,200,true],['slashL',true,200,false],['slashL',true,.001,true],['slashL',true,.001,false],['slashL',true,0,true]]){
  Object.assign(ctx,{testAttack:attack,testAim:aim,testTwist:twist,test3D:momentum3D});
  await vm.runInContext('settings.jumpEvents[0].attack=testAttack;settings.jumpEvents[0].twist=testTwist;settings.aim=testAim;settings.momentum3D=test3D;runKey=null;prepareRun({preserveTime:true})',ctx);
  const row=vm.runInContext(`(()=>{
   const segment=flight.segments[0],track=segment.attack,pelvis=names.indexOf('pelvis'),up=R.rotate(R.qinv(idle.q[pelvis]),[0,1,0]),tilt=p=>Math.acos(Math.max(-1,Math.min(1,R.rotate(p.q[pelvis],up)[1])))*180/Math.PI;
   const samples=[track?.hitTime||.79,track?.end||.97,track?.returnEnd||1.3,1.5,2.083333,3].map(t=>{const frame=flight.sample(t),pose=physics.target(aimTimelinePoseAt(t)),raw=segment.spin.sample(t),rot=frame.physical?.rotation;return {t,tilt:tilt(pose),rawTilt:tilt(raw.pose),rotation:rot,momentum:frame.physical?.momentum,target:frame.physical?.target,spinAxis:frame.spin?.spinAxis,pelvis:pose.q[pelvis]};});
   return {attack:testAttack,aim:testAim,twist:testTwist,momentum3D:test3D,samples};
  })()`,ctx);report.push(row);console.log(JSON.stringify({...row,samples:row.samples.map(({t,tilt,rawTilt})=>({t,tilt,rawTilt}))}));
 }
 fs.writeFileSync(new URL('../../Saved/BodyflipLab/TwistAttackAudit/return-audit.json',import.meta.url),JSON.stringify(report,null,2));
}finally{physics?.dispose();}
