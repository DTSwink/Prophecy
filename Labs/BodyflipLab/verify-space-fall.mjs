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
fixture.settings.momentum3D=false;
try{
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(file,import.meta.url),'utf8');if(file==='physical-aim.js')code=code.replace('const statistics={evaluations:0}', 'root.__aimInputs ||= []; root.__aimInputs.push({rawSource:originalSource,physicalOptions,track,clip,settings,project,worldPose});const statistics={evaluations:0}');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}

 await vm.runInContext('init()',ctx);
 assert.equal(vm.runInContext('settings.spaceFallAnimation',ctx),false);
 assert.equal(ids.get('spaceFallAnimation').disabled,false);
 const before=vm.runInContext('JSON.stringify(physics.target(aimTimelinePoseAt(.7942017484572588)))',ctx);
 vm.runInContext('setPlaying(true)',ctx);ids.get('spaceFallAnimation').checked=true;await ids.get('spaceFallAnimation').onchange();
 assert(ctx.BodyflipLab.state.playing,'playing resumes after option rebuild');
 assert.equal(vm.runInContext('settings.spaceFallAnimation',ctx),true);
 assert(vm.runInContext("(()=>{const saved=BodyflipScenes.snapshot({settings,playback:{}}),copy=JSON.parse(JSON.stringify(saved));return C.sanitize(copy.settings).spaceFallAnimation&&BodyflipScenes.switchMode(BodyflipScenes.switchMode(copy,'idle'),'spaceGym').settings.spaceFallAnimation;})()",ctx),'option survives save and mode switches');
 const result=vm.runInContext(`(()=>{
  const segment=flight.segments[0],track=segment.attack,plan=segment.physical.track.plan,pose=physics.target(aimTimelinePoseAt(track.hitTime)),center=BodyflipAttackAim.center(pose,plan.rig),error=R.length(R.sub(R.unit(R.sub(plan.point(pose),center)),R.unit(R.sub(settings.target,center))));
  const baseline=(fall,events=[])=>BodyflipSpace.sequence(run,jumps,{...settings,spaceFallAnimation:fall,airFlip:false},parents,events,vanillaAttacks,idle);
  const off=baseline(false),on=baseline(true),delayed=baseline(true,[{...segment.event,attack:'none',twist:0,flip:0}]);
  const locals=p=>R.localize(p.points,p.q,parents),difference=(a,b)=>Math.max(...a.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(b.q[i]))))));
  const early=difference(delayed.sample(.1).pose,off.sample(.1).pose),entry=difference(delayed.sample(segment.event.time-1e-7).pose,delayed.sample(segment.event.time+1e-7).pose);
  const changed=difference(on.sample(1.5).pose,off.sample(1.5).pose),loopMoving=difference(on.sample(1.5).pose,on.sample(1.7).pose);
  let drift=0,lengthError=0,carrierError=0;
  for(const time of [0,.1,.4,1,1.5,2]){const a=on.sample(time),b=off.sample(time),al=locals(a.pose),bl=locals(b.pose);drift=Math.max(drift,R.length(R.sub(a.root,b.root)),R.length(a.velocity));carrierError=Math.max(carrierError,...[0,1].map(i=>R.length(R.qlog(R.qm(al.q[i],R.qinv(bl.q[i]))))));lengthError=Math.max(lengthError,...al.p.map((p,i)=>Math.abs(R.length(p)-R.length(bl.p[i]))));}
  const saved=JSON.stringify(on.sample(1.5));on.sample(4);on.sample(.1);const seekSame=saved===JSON.stringify(on.sample(1.5));
  const input=__aimInputs.at(-1),time=track.returnEnd+.1,raw=locals(input.rawSource(time).pose),actual=locals(physics.target(aimTimelinePoseAt(time))),returnError=Math.max(...names.slice(2).map((_,j)=>R.length(R.qlog(R.qm(raw.q[j+2],R.qinv(actual.q[j+2]))))));
  return {error,early,entry,changed,loopMoving,drift,lengthError,carrierError,seekSame,returnError,phase:flight.sample(time).phase};
 })()`,ctx);
 assert(result.error<1e-5,'aim includes the falling base');assert(result.early<1e-10,'idle before first marker');assert(result.entry<1e-5,'smooth fall entry');assert(result.changed>.1&&result.loopMoving>.001,'authored falling loop plays');assert(result.drift<1e-12,'no gravity or drift added');assert(result.lengthError<1e-9,'bone lengths preserved');assert(result.carrierError<1e-8,'root and pelvis orientation retained');assert(result.seekSame,'deterministic seeking');assert(result.returnError<1e-7,'attack returns to ongoing fall articulation');assert.equal(result.phase,'FALL LOOP');
 vm.runInContext('setPlaying(false)',ctx);ids.get('spaceFallAnimation').checked=false;await ids.get('spaceFallAnimation').onchange();
 assert(!ctx.BodyflipLab.state.playing,'paused remains paused');assert.equal(vm.runInContext('JSON.stringify(physics.target(aimTimelinePoseAt(.7942017484572588)))',ctx),before,'off restores the original result');
 vm.runInContext("settings.mode='idle';syncControls()",ctx);assert(ids.get('spaceFallAnimation').disabled,'Space-only option disabled outside Space');
 assert.equal(ctx.BodyflipLab.state.errors.length,0);assert.equal(worlds,1);
 console.log(JSON.stringify({passed:true,...result,liveWrites:0}));
}finally{physics?.dispose();}
