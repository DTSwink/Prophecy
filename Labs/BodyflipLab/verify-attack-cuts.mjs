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
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(file,import.meta.url),'utf8');if(file==='physical-aim.js')code=code.replace('return {sample,prepare,statistics,','return {sample,prepare,statistics,neutralSample:neutral.sample,').replace('const statistics={evaluations:0}', 'root.__aimInputs ||= []; root.__aimInputs.push({rawSource:originalSource,physicalOptions,track,clip,settings,project,worldPose});const statistics={evaluations:0}');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}

 await vm.runInContext('init()',ctx);
 ids.get('attackEndOptions').open=true;await ids.get('attackEndOptions').ontoggle();
 const fields=ids.get('attackEndFields').children.map(row=>row.children[0]);assert.equal(fields.length,19);const rows=[];
 // Defaults must be actual input values, otherwise native number arrows start at min.
 vm.runInContext('settings.attackEndFrames={};settings.sweepKickEndFrame=35;syncAttackEnds()',ctx);
 for(const field of fields)assert.notEqual(String(field.value),'','numeric default '+field.dataset.attack);
 const ru=fields.find(i=>i.dataset.attack==='slashRU');assert.equal(+ru.value,24);
 ru.value=String(+ru.value-1);ru.oninput();assert.equal(vm.runInContext('settings.attackEndFrames.slashRU',ctx),23);
 ru.value='';ru.oninput();vm.runInContext('syncAttackEnds()',ctx);assert.equal(+ru.value,24);assert(vm.runInContext('settings.attackEndFrames.slashRU===undefined',ctx));

 for(const input of fields){
  ctx.testAttack=input.dataset.attack;ctx.cut=+input.min;
  vm.runInContext("settings.jumpEvents=[{...settings.jumpEvents[0],enabled:true,attack:testAttack,throwCharge:100,throwSpeed:1,pose:'none',flip:0,twist:0}];setPlaying(true)",ctx);
  input.value=ctx.cut;input.oninput();await input.onchange();assert(ctx.BodyflipLab.state.playing,'resume '+ctx.testAttack);
  const row=vm.runInContext(`(()=>{const tr=flight.segments[0].attack;return {attack:testAttack,cut,stored:settings.attackEndFrames[testAttack],end:tr.end,hit:tr.hitTime,phase:flight.sample(tr.end+1e-6).attack?.phase,finite:flight.sample(tr.returnEnd-.01).pose.q.flat().every(Number.isFinite),sourceEnd:tr.plan?.track?.sourceEnd};})()`,ctx);console.log(JSON.stringify(row));rows.push(row);assert.equal(row.stored,row.cut);assert(row.end>=row.hit-1e-9);assert.equal(row.phase,'RETURN');assert(row.finite);
 }
 assert(vm.runInContext("JSON.stringify(C.sanitize(JSON.parse(JSON.stringify(stored().settings))).attackEndFrames)===JSON.stringify(settings.attackEndFrames)",ctx),'roundtrip independent endings');
 const input=fields.find(i=>i.dataset.attack==='slashL');input.value='';input.oninput();await input.onchange();assert(vm.runInContext("settings.attackEndFrames.slashL===undefined&&settings.attackEndFrames.KickL===13",ctx),'clear only selected override');
 console.log(JSON.stringify({passed:true,attacks:rows.length,liveWrites:0}));
}finally{physics?.dispose();}
