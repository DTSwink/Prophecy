// Full browser-script order and app initialization using an in-memory DOM/GL sink.
// Real local data and the app's single Jolt world; no browser or live state writes.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js');globalThis.Recovery=R;
const {createPhysics}=await import('./physics.mjs');let worlds=0,physics;
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8'),ids=new Map(),gl=new Proxy({getShaderParameter:()=>true,getProgramParameter:()=>true,getAttribLocation:()=>0,getUniformLocation:()=>({})},{get:(t,k)=>t[k]??(k.toUpperCase()===k?1:()=>({}))});
class Element{constructor(tag='div'){this.tagName=tag.toUpperCase();this.value='';this.children=[];this.dataset={};this.style={setProperty(){}};this.attrs={};this.classList={add(){},remove(){},toggle(){},contains(){return false;}};this.parentElement={classList:this.classList,insertBefore(){}};this.textContent='';this.clientWidth=1280;this.clientHeight=720;}
 get childNodes(){return this.children;} append(...a){for(const x of a){x.parent=this;this.children.push(x);}}replaceChildren(...a){this.children=[];this.append(...a);}remove(){if(this.parent)this.parent.children=this.parent.children.filter(e=>e!==this);}setAttribute(k,v){this.attrs[k]=v;}getAttribute(k){return this.attrs[k];}addEventListener(){}getBoundingClientRect(){return {left:0,top:0,width:1280,height:720};}getContext(){return gl;}setPointerCapture(){}contains(e){return this===e||this.children.some(x=>x.contains(e));}closest(){return null;}matches(){return false;}focus(){}blur(){} }
for(const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g)){const e=new Element(m[1]);e.id=m[2];for(const a of m[0].matchAll(/([\w-]+)="([^"]*)"/g))e.attrs[a[1]]=a[2];e.value=e.attrs.value||'';e.type=e.attrs.type||'';ids.set(e.id,e);}
const footer=new Element(),document={body:new Element('body'),hidden:false,activeElement:null,getElementById:id=>ids.get(id)||null,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),addEventListener(){},querySelector:()=>footer,querySelectorAll:selector=>selector.includes('axisGrid')?ids.get('axisGrid').children:[]};
const defaultFixture={settings:{mode:'spaceGym',motion:'kinematic',aim:false,ramps:false,surfaceIK:false,trimOut:1.4,jumpEvents:[{id:'a',time:.1,jumpPercent:0,attack:'big-throw',flip:0,twist:0,spinVersion:2}]},playback:{time:0,playing:false}};
const fixture=JSON.parse(process.env.BODYFLIP_PARITY_FIXTURE||JSON.stringify(defaultFixture));
function fakeNN(r){const last=r.seeds.at(-1),origin=last.points[0];return {names:r.names.slice(1),fps:30,duration:(r.frames-1)/30,roots:r.roots.slice(0,r.frames),poses:Array.from({length:r.frames},(_,i)=>({points:last.points.slice(1).map(p=>p.map((v,k)=>v-origin[k]+r.roots[i][k])),axes:last.axes.slice(1)}))};}
const fetched=[],writes=[];let timers=0;
const ctx=vm.createContext({document,console,structuredClone,performance,URL,TextEncoder,TextDecoder,Float32Array,Float64Array,Int32Array,Uint8Array,ArrayBuffer,Buffer,Math,Date,Map,Set,WeakMap,WeakSet,atob,devicePixelRatio:1,ResizeObserver:class{observe(){}},Option:function(text,value){const e=new Element('option');e.textContent=text;e.value=value;return e;},setTimeout:()=>++timers,clearTimeout(){},requestAnimationFrame:()=>1,cancelAnimationFrame(){},location:{reload(){}},crypto:{randomUUID:()=> 'test'},fetch:async(path,options)=>{fetched.push(path);if(options?.method==='POST'){if(path==='/resume')return {ok:true,json:async()=>fakeNN(JSON.parse(options.body))};writes.push(path);return {ok:true,json:async()=>({})};}if(path==='/state')return {ok:true,json:async()=>structuredClone(fixture)};const bytes=fs.readFileSync(new URL(path,import.meta.url));return {ok:true,json:async()=>JSON.parse(bytes),arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};},__createPhysics:async(...a)=>{worlds++;physics=await createPhysics(...a);return physics;}});ctx.window=ctx;ctx.addEventListener=()=>{};
const scripts=[...html.matchAll(/<script src="([^"]+)"/g)].map(m=>m[1]);

const native=vm.createContext({Date,performance,console,__bodyflipAttack:id=>fs.readFileSync(new URL('../../Content/BodyflipLab/Attacks/'+id+'.json',import.meta.url),'utf8'),__bodyflipNN:json=>JSON.stringify(fakeNN(JSON.parse(json)))});
vm.runInContext(fs.readFileSync(new URL('../../Content/BodyflipLab/Runtime.js',import.meta.url),'utf8'),native);
const call=input=>JSON.parse(vm.runInContext('BodyflipNative.command('+JSON.stringify(JSON.stringify(input))+')',native));
let maxPosition=0,maxRotation=0;const rows=[];
try{
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(file,import.meta.url),'utf8');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}
 await vm.runInContext('init()',ctx);assert.equal(ctx.BodyflipLab.state.errors.length,0);
 call({op:'assets',value:JSON.parse(fs.readFileSync(new URL('../../Content/BodyflipLab/Assets.json',import.meta.url),'utf8'))});
 call({op:'start',settings:fixture.settings,horizon:fixture.settings.trimOut});
 for(const t of fixture.times||[0,.1,.3,.5,.8,1.2]){
  await ctx.BodyflipLab.seek(t);assert.equal(ctx.BodyflipLab.state.errors.length,0);
  const app=vm.runInContext('({pose:currentPose,phase:flightFrame?.phase,root:flightFrame?.root})',ctx),port=call({op:'sample',time:t});
  let position=0,angle=0;
  for(let i=0;i<app.pose.q.length;i++){
   position=Math.max(position,Math.hypot(...app.pose.points[i].map((v,k)=>v-port.pose.points[i][k])));
   angle=Math.max(angle,2*Math.acos(Math.min(1,Math.abs(app.pose.q[i].reduce((s,v,k)=>s+v*port.pose.q[i][k],0)))));
  }
  rows.push({time:t,phase:app.phase,nativePhase:port.phase,position,angle});maxPosition=Math.max(maxPosition,position);maxRotation=Math.max(maxRotation,angle);
 }
 const report={name:fixture.name||'throw',frames:rows.length,maxPosition,maxRotation,rows};console.log(JSON.stringify(report,null,2));
 assert(maxPosition<1e-8,'Native adapter differs from actual app positions: '+maxPosition);
 assert(maxRotation<1e-6,'Native adapter differs from actual app rotations: '+maxRotation);
 assert.equal(worlds,1);assert(writes.every(p=>p==='/state'));
}finally{physics?.dispose();}
