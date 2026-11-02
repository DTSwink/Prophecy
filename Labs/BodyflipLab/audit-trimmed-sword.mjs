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
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(file,import.meta.url),'utf8');if(file==='physical-aim.js')code=code.replace('const statistics={evaluations:0}', 'root.__aimInputs ||= []; root.__aimInputs.push({rawSource:originalSource,physicalOptions,track,clip,settings,project,worldPose});const statistics={evaluations:0}');if(file==='jump-attack.js')code=code.replace('const track={coupledHand,returnPolicy,sample,','const track={debug:{entry,uncorrected,displayed},coupledHand,returnPolicy,sample,');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}

 await vm.runInContext('init()',ctx);

 const report=vm.runInContext(`(()=>{
 const track=flight.segments[0].attack,hand=names.indexOf('hand_r'),local=p=>R.localize(p.points,p.q,parents).q,angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI;
 const clip=vanillaAttacks.get('slashLU');const stages={source:t=>R.fk(BodyflipJumpAttack.attackAt(clip,track.sourceFrame(t-track.start),names,parents,settings.distributePelvisTurn),parents),entry:t=>track.debug.entry(t),raw:t=>track.debug.uncorrected(t),comp:t=>track.debug.displayed(t),track:t=>track.sample(t).pose,flight:t=>flight.sample(t).pose,aim:t=>aimTimelinePoseAt(t),display:t=>physics.target(aimTimelinePoseAt(t))},summary={},frames=[];
 let prev={};
 for(let time=track.end-.05;time<track.returnEnd+.1;time+=1/240){const row={time,poses:{}};for(const [name,fn] of Object.entries(stages)){const pose=fn(time),q=local(pose);row.poses[name]=pose;summary[name]||={steps:[],hand:[]};if(prev[name]){const dif=q.map((v,i)=>angle(v,prev[name].q[i]));summary[name].steps.push({time,bone:names[dif.indexOf(Math.max(...dif))],angle:Math.max(...dif)});summary[name].hand.push({time,local:angle(q[hand],prev[name].q[hand]),world:angle(pose.q[hand],prev[name].pose.q[hand])});}prev[name]={q,pose};}frames.push(row);}
 for(const s of Object.values(summary)){s.steps.sort((a,b)=>b.angle-a.angle);s.steps=s.steps.slice(0,8);s.hand.sort((a,b)=>b.world-a.world);s.hand=s.hand.slice(0,8);}
 const boundaries=[track.end,track.returnEnd].map(time=>({time,stages:Object.fromEntries(Object.entries(stages).map(([name,fn])=>{const a=local(fn(time-1e-7)),b=local(fn(time+1e-7));return [name,a.map((q,i)=>({bone:names[i],angle:angle(q,b[i])})).sort((a,b)=>b.angle-a.angle).slice(0,3)];}))}));
 return {timing:{start:track.start,hit:track.hitTime,end:track.end,returnEnd:track.returnEnd},summary,boundaries,names,parents,frames};
 })()`,ctx);

 const picked=Array.from({length:7},(_,i)=>report.timing.end+(report.timing.returnEnd-report.timing.end)*i/6);
 vm.runInContext("globalThis.meshRenderer=Object.create(WebGLMotionRenderer.prototype);meshRenderer.torsoColliders=BodyflipTorso.create(names,parents,idle);globalThis.meshFor=pose=>{const m=new LabVertexStream(100000);meshRenderer.addBody(m,{...pose,bicolor:true});meshRenderer.addSword(m,pose);return m.view();}",ctx);
 const chunks=[],index=[];let offset=0;
 for(let i=0;i<picked.length;i++){const frame=report.frames.reduce((a,b)=>Math.abs(a.time-picked[i])<Math.abs(b.time-picked[i])?a:b);ctx.renderPose=frame.poses.display;const mesh=vm.runInContext('meshFor(renderPose)',ctx),bytes=Buffer.from(mesh.buffer,mesh.byteOffset,mesh.byteLength);chunks.push(bytes);index.push({frame:i,row:0,offset,count:mesh.length,time:frame.time});offset+=bytes.length;}
 fs.mkdirSync(new URL('../../Saved/BodyflipLab/TrimmedSword',import.meta.url),{recursive:true});
 fs.writeFileSync(new URL('../../Saved/BodyflipLab/TrimmedSword/meshes.bin',import.meta.url),Buffer.concat(chunks));
 fs.writeFileSync(new URL('../../Saved/BodyflipLab/TrimmedSword/mesh-index.json',import.meta.url),JSON.stringify({index,origin:[0,1,0]}));
 fs.writeFileSync(new URL('../../Saved/BodyflipLab/trimmed-sword-audit.json',import.meta.url),JSON.stringify(report));
 console.log(JSON.stringify({timing:report.timing,summary:Object.fromEntries(Object.entries(report.summary).map(([k,v])=>[k,{steps:v.steps.slice(0,1),hand:v.hand.slice(0,1)}])),boundaries:report.boundaries},null,2));
}finally{physics?.dispose();}
