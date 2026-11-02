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
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(file,import.meta.url),'utf8');if(file==='physical-aim.js')code=code.replace('const statistics={evaluations:0}', 'root.__aimInputs ||= []; root.__aimInputs.push({rawSource:originalSource,physicalOptions,track,clip,settings,project,worldPose});const statistics={evaluations:0}');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}

 await vm.runInContext('init()',ctx);
 const report=vm.runInContext(`(()=>{
 const segment=flight.segments[0],track=segment.attack,rec=track.plan.track,response=track.plan.response,clip=vanillaAttacks.get('sweepKick');
 const local=p=>R.localize(p.points,p.q,parents).q,angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI;
 const raw=t=>{const f=Math.max(0,Math.min(clip.poses.length-1,rec.sourceFrame(t-track.start))),i=Math.min(clip.poses.length-2,Math.floor(f));return C.blend(clip.poses[i],clip.poses[i+1],f-i,parents);};
 const stages={source:raw,recorded:t=>rec.sample(t-track.start),balanced:t=>response.sample(t-track.start),integrated:t=>track.sample(t).pose,aimed:t=>aimTimelinePoseAt(t),displayed:t=>physics.target(aimTimelinePoseAt(t))};
 const summary={},frames=[],dt=1/240;let previous={};
 for(let i=0;i<=Math.ceil((track.returnEnd-track.start+.1)/dt);i++){
  const time=track.start+i*dt,poses=Object.fromEntries(Object.entries(stages).map(([n,fn])=>[n,fn(time)]));
  for(const [stage,pose] of Object.entries(poses)){const q=local(pose);summary[stage]||={steps:[],legSteps:[],perBone:{},max:0};if(previous[stage]){const dif=q.map((v,j)=>angle(v,previous[stage][j])),max=Math.max(...dif);summary[stage].max=Math.max(max,summary[stage].max);dif.forEach((v,j)=>{if(v>(summary[stage].perBone[names[j]]?.degrees||0))summary[stage].perBone[names[j]]={time,degrees:v};});const ld=dif.map((v,j)=>/^(thigh|calf|foot)_/.test(names[j])?v:0),lm=Math.max(...ld);summary[stage].legSteps.push({time,bone:names[ld.indexOf(lm)],degrees:lm});summary[stage].steps.push({time,bone:names[dif.indexOf(max)],degrees:max});}previous[stage]=q;}
  if(i%4===0)frames.push({time,sourceFrame:rec.sourceFrame(time-track.start),poses});
 }
 for(const s of Object.values(summary)){s.steps=s.steps.sort((a,b)=>b.degrees-a.degrees).slice(0,4);s.legSteps=s.legSteps.sort((a,b)=>b.degrees-a.degrees).slice(0,6);}
 const selected=[track.start+rec.lead,track.hitTime,1.6833333333333,track.end,track.returnEnd-1/60,track.returnEnd];
 const differences=selected.map(time=>{const poses=Object.fromEntries(Object.entries(stages).map(([n,fn])=>[n,fn(time)])),q=Object.fromEntries(Object.entries(poses).map(([n,p])=>[n,local(p)]));return {time,sourceFrame:rec.sourceFrame(time-track.start),diff:Object.fromEntries([['retarget','source','recorded'],['balance','recorded','balanced'],['aim','integrated','aimed'],['project','aimed','displayed']].map(([label,a,b])=>[label,names.map((n,j)=>({bone:n,degrees:angle(q[a][j],q[b][j])})).sort((a,b)=>b.degrees-a.degrees).slice(0,6)]))};});
 const boundary=[track.end,track.returnEnd].map(t=>({time:t,stages:Object.fromEntries(Object.entries(stages).filter(([n])=>n!=='source').map(([n,fn])=>{const a=local(fn(t-1e-7)),b=local(fn(t+1e-7));return [n,names.map((bone,j)=>({bone,degrees:angle(a[j],b[j])})).sort((a,b)=>b.degrees-a.degrees).slice(0,3)];}))}));
 return {boundary,settings,timing:{start:track.start,lead:rec.lead,hit:track.hitTime,end:track.end,returnEnd:track.returnEnd},spinActive:segment.spin.active,summary,differences,names,parents,frames,source:clip.meta};
 })()`,ctx);
 fs.mkdirSync(new URL('../../Saved/BodyflipLab/SweepCurrent',import.meta.url),{recursive:true});
 fs.writeFileSync(new URL('../../Saved/BodyflipLab/SweepCurrent/audit.json',import.meta.url),JSON.stringify(report));
 console.log(JSON.stringify({timing:report.timing}));
 const picked=[1.0,report.timing.hit,1.4,1.6833333333,report.timing.returnEnd],stages=['source','balanced','displayed'];
 vm.runInContext("globalThis.meshRenderer=Object.create(WebGLMotionRenderer.prototype);meshRenderer.torsoColliders=BodyflipTorso.create(names,parents,idle);globalThis.meshFor=pose=>{const m=new LabVertexStream(50000);meshRenderer.addBody(m,{...pose,bicolor:true,hideSword:true});return m.view();}",ctx);
 const index=[],chunks=[];let offset=0;
 for(let f=0;f<picked.length;f++){const frame=report.frames.reduce((a,b)=>Math.abs(a.time-picked[f])<Math.abs(b.time-picked[f])?a:b);for(let row=0;row<stages.length;row++){
  ctx.renderPose=frame.poses[stages[row]];const mesh=vm.runInContext('meshFor(renderPose)',ctx),bytes=Buffer.from(mesh.buffer,mesh.byteOffset,mesh.byteLength);chunks.push(bytes);index.push({frame:f,row,offset,count:mesh.length,time:frame.time});offset+=bytes.length;
 }}
 fs.writeFileSync(new URL('../../Saved/BodyflipLab/SweepCurrent/meshes.bin',import.meta.url),Buffer.concat(chunks));
 fs.writeFileSync(new URL('../../Saved/BodyflipLab/SweepCurrent/mesh-index.json',import.meta.url),JSON.stringify({index,origin:[0,1,0],rows:stages}));
}finally{physics?.dispose();}
