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
const fixture={settings:{mode:'spaceGym',kickToArmed:true,motion:'kinematic',aim:false,ramps:false,surfaceIK:false,trimOut:1.4,jumpEvents:[{id:'a',time:.1,jumpPercent:0,attack:'big-throw',flip:0,twist:0,spinVersion:2}]},playback:{time:0,playing:false}};
const fetched=[],writes=[];let timers=0;
const ctx=vm.createContext({document,console,structuredClone,performance,URL,TextEncoder,TextDecoder,Float32Array,Float64Array,Int32Array,Uint8Array,ArrayBuffer,Buffer,Math,Date,Map,Set,WeakMap,WeakSet,atob,devicePixelRatio:1,ResizeObserver:class{observe(){}},Option:function(text,value){const e=new Element('option');e.textContent=text;e.value=value;return e;},setTimeout:()=>++timers,clearTimeout(){},requestAnimationFrame:()=>1,cancelAnimationFrame(){},location:{reload(){}},crypto:{randomUUID:()=> 'test'},fetch:async(path,options)=>{fetched.push(path);if(options?.method==='POST'){writes.push(path);return {ok:true,json:async()=>({})};}if(path==='/state')return {ok:true,json:async()=>structuredClone(fixture)};const bytes=fs.readFileSync(new URL(path,import.meta.url));return {ok:true,json:async()=>JSON.parse(bytes),arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};},__createPhysics:async(...a)=>{worlds++;physics=await createPhysics(...a);return physics;}});ctx.window=ctx;ctx.addEventListener=()=>{};
const scripts=[...html.matchAll(/<script src="([^"]+)"/g)].map(m=>m[1]);
ctx.setTimeout=(callback,delay=0)=>{if(delay===0)queueMicrotask(callback);return ++timers;};
try{
 for(const file of scripts){if(file==='shared-foot-ik.js')continue;let code=fs.readFileSync(new URL(file,import.meta.url),'utf8');if(file==='app.js')code=code.replace("await import('./physics.mjs')","({createPhysics:__createPhysics})").replace('init().catch(fail);','');vm.runInContext(code,ctx,{filename:file});}
 await vm.runInContext('init()',ctx);assert.equal(worlds,1);assert(ctx.BodyflipLab);assert.equal(ctx.BodyflipLab.state.errors.length,0);assert(fetched.includes('data/throws.json'));assert(ids.get('jumpAttack').children.some(e=>e.value==='big-throw'));assert(ids.get('jumpAttack').children.some(e=>e.value==='small-throw'));
 vm.runInContext("jumpTrack.selected='a';jumpTrack.open=true;jumpTrack.sync()",ctx);assert.equal(ids.get('jumpThrowFields').hidden,false);assert.equal(ids.get('jumpThrowCharge').disabled,true);
 await ctx.BodyflipLab.seek(.8);assert.equal(ctx.BodyflipLab.state.errors.length,0);assert.equal(vm.runInContext('throwController.plans.length',ctx),1);assert.equal(vm.runInContext('throwController.sample(simTime,currentPose).length',ctx),1);
 vm.runInContext('const projectileProbe=throwController.sample(simTime,currentPose).find(p=>!String(p.id).startsWith("held:"));settings.target=BodyflipAttackAim.launchCenter(projectileProbe);measureAttackContact()',ctx);
 assert.equal(ctx.BodyflipLab.state.hit,true,'released projectile, not hand, is used for hit readout');
 // Exercise target input and drag-preview redraws after the scaled spear is released.
 vm.runInContext('settings.aim=true;refreshAim()',ctx);
 for(let i=0;i<6;i++){
  const before=vm.runInContext('JSON.stringify(throwController.plans)',ctx);
  ids.get('targetX').value=String(-1+i*.3);ids.get('targetX').oninput();
  assert.notEqual(vm.runInContext('JSON.stringify(throwController.plans)',ctx),before);
  vm.runInContext('settings.target[2]+=.1;refreshAim({preview:true});refreshAim()',ctx);
  assert(vm.runInContext('(()=>{const p=throwController.plans[0],track=throwController.tracks[0],plan=aimPlans.get(track);return R.length(R.sub(R.unit(p.axis),plan.throwDirectionFor(settings.target)));})()',ctx)<1e-6,'app release spear shaft follows frozen world direction');
  assert(vm.runInContext('(()=>{const p=throwController.plans[0],track=throwController.tracks[0];return Math.abs(R.length(p.v)-R.length(track.model.launch.v));})()',ctx)<.01,'stationary carrier preserves final manifest launch speed');
  assert.equal(physics.projectileDiagnostics().bodies,1);
  assert.equal(ctx.BodyflipLab.state.errors.length,0);
 }
 assert(fetched.includes('data/throw-reference.json'),'approved reference loaded');
 const beforeReference=vm.runInContext('JSON.stringify({plans:throwController.plans,physics:physics.projectileDiagnostics(),time:simTime,pose:currentPose,settings})',ctx);
 vm.runInContext('let referenceMeshVertices=0;const originalAddProjectiles=renderer.addProjectiles;renderer.addProjectiles=function(mesh,items){const before=mesh.length;originalAddProjectiles.call(this,mesh,items);referenceMeshVertices+=mesh.length-before;}',ctx);
 ids.get('vanillaOnly').checked=true;ids.get('vanillaOnly').onchange();
 assert(ids.get('phase').textContent.includes('THROW LAB REFERENCE big-throw'),'reference labelled accurately');
 assert(vm.runInContext('referenceMeshVertices',ctx)>0,'reference spear actually reaches renderer');
 assert(vm.runInContext('vanillaView().referenceScene.radius>0',ctx),'reference collision target displayed');
 ids.get('vanillaOnly').checked=false;ids.get('vanillaOnly').onchange();
 assert.equal(vm.runInContext('JSON.stringify({plans:throwController.plans,physics:physics.projectileDiagnostics(),time:simTime,pose:currentPose,settings})',ctx),beforeReference,'reference toggle preserves simulation and tuning');
 assert(vm.runInContext('(()=>{const p=throwController.plans[0];return R.length(R.cross(R.unit(p.axis),p.omega));})()',ctx)<1e-8,'actual spawn has axial spear spin');
 ids.get('attackReturnExponent').value='.5';ids.get('attackReturnExponent').oninput();await ids.get('attackReturnExponent').onchange();
 assert.equal(vm.runInContext('settings.attackReturnExponent',ctx),.5,'retained exponent value');assert.equal(ids.get('attackReturnExponentRead').textContent,'0.50');
 ids.get('attackReturnLerp').value='20';ids.get('attackReturnLerp').oninput();await ids.get('attackReturnLerp').onchange();
 assert.equal(vm.runInContext('settings.attackReturnLerp',ctx),.2,'retained lerp value');
 assert.equal(vm.runInContext('throwController.tracks[0].returnPolicy.horizon',ctx),.25,'sliders do not alter duration return');
 ids.get('bigThrowReturnFrames').value='8';ids.get('bigThrowReturnFrames').oninput();await ids.get('bigThrowReturnFrames').onchange();
 assert(Math.abs(vm.runInContext('throwController.tracks[0].end-throwController.tracks[0].releaseTime',ctx)-8/60)<1e-9,'More options marker uses frames after release');
 for(const direct of [false,true]){ctx.testDirect=direct;vm.runInContext('settings.kickToArmed=testDirect;settings.attackRate=2;manualResponse=null;attackTime=0;manualSoft(currentPose,currentPose)',ctx);assert.equal(vm.runInContext('manualResponse.response.returnPolicy.horizon',ctx),.45,'manual attack uses original return duration');assert.equal(vm.runInContext('total()',ctx),vm.runInContext('manualResponse.response.returnEnd',ctx),'manual playback lasts through timed return');assert(Math.abs(vm.runInContext('manualResponse.response.returnPolicy.factor(.225)',ctx)-.5)<1e-9,'manual return half weight at half duration');}
 ids.get('attackReturnDistance').value='1';ids.get('attackReturnDistance').oninput();await ids.get('attackReturnDistance').onchange();
 assert.equal(vm.runInContext('settings.attackReturnDistance',ctx),1,'distance slider value');assert.equal(ids.get('attackReturnDistanceRead').textContent,'1.00');
 assert(vm.runInContext('(()=>{const t=throwController.tracks[0];return Math.abs(t.returnEnd-t.end-C.returnDuration(.25,t.returnDistance,1))<1e-9;})()',ctx),'actual throw uses distance-selected duration');
 const scaledDuration=vm.runInContext('throwController.tracks[0].returnEnd-throwController.tracks[0].end',ctx);assert(scaledDuration>0);
 await vm.runInContext('BodyflipLab.seek(throwController.tracks[0].returnEnd+.01)',ctx);
 assert.equal(ctx.BodyflipLab.state.errors.length,0,'scaled return playback');
 await vm.runInContext('settings.target=[2,2,-2];refreshAim()',ctx);assert.equal(ctx.BodyflipLab.state.errors.length,0,'distance-aware retarget rebuild');
 assert(vm.runInContext('(()=>{const t=throwController.tracks[0];return Math.abs(t.returnEnd-t.end-C.returnDuration(.25,t.returnDistance,1))<1e-9;})()',ctx),'retarget recomputes frozen duration');
 vm.runInContext('jumpTrack.selected=null;jumpTrack.sync()',ctx);
 assert.equal(ids.get('attackReturnDuration').disabled,false,'duration stays enabled without marker selection');
 ids.get('attackReturnDistance').value='0';ids.get('attackReturnDistance').oninput();await ids.get('attackReturnDistance').onchange();
 ids.get('attackReturnDuration').value='.6';ids.get('attackReturnDuration').oninput();await ids.get('attackReturnDuration').onchange();
 assert.equal(vm.runInContext('settings.attackReturnDuration',ctx),.6);assert.equal(ids.get('attackReturnDurationRead').textContent,'0.60 s');
 assert.equal(vm.runInContext('throwController.tracks[0].returnPolicy.horizon',ctx),.6,'always-enabled duration changes actual throw');
 vm.runInContext('manualResponse=null;attackTime=0;manualSoft(currentPose,currentPose)',ctx);
 assert.equal(vm.runInContext('manualResponse.response.returnPolicy.horizon',ctx),.6,'duration also changes manual attack');
 // Option edits retain playback intent, including coalesced and superseded jobs.
 vm.runInContext('setPlaying(true)',ctx);
 ids.get('attackReturnDuration').value='.65';ids.get('attackReturnDuration').oninput();assert(!ctx.BodyflipLab.state.playing,'temporarily pauses during slider edit');await ids.get('attackReturnDuration').onchange();assert(ctx.BodyflipLab.state.playing,'slider rebuild resumes');
 ids.get('attackReturnDuration').oninput();await ids.get('attackReturnDuration').onchange();assert(ctx.BodyflipLab.state.playing,'unchanged slider resumes without rebuild');
 vm.runInContext('setPlaying(false)',ctx);ids.get('fallCap').value='21';ids.get('fallCap').oninput();await ids.get('fallCap').onchange();assert(!ctx.BodyflipLab.state.playing,'paused stays paused');
 vm.runInContext('setPlaying(true);globalThis.savedPrepare=F.prepare;globalThis.preparationGate=new Promise(resolve=>globalThis.releasePreparation=resolve);F.prepare=async(...args)=>{await preparationGate;return savedPrepare(...args);}',ctx);
 ids.get('attackReturnDuration').value='.7';ids.get('attackReturnDuration').oninput();const firstEdit=ids.get('attackReturnDuration').onchange();
 ids.get('attackReturnDuration').value='.8';ids.get('attackReturnDuration').oninput();const lastEdit=ids.get('attackReturnDuration').onchange();
 vm.runInContext('releasePreparation()',ctx);await Promise.all([firstEdit,lastEdit]);assert(ctx.BodyflipLab.state.playing,'latest of rapid edits resumes');
 vm.runInContext('globalThis.preparationGate=new Promise(resolve=>globalThis.releasePreparation=resolve)',ctx);
 ids.get('attackReturnDuration').value='.9';ids.get('attackReturnDuration').oninput();const pendingEdit=ids.get('attackReturnDuration').onchange();
 ids.get('attackReturnDuration').oninput();const coalescedEdit=ids.get('attackReturnDuration').onchange();
 vm.runInContext('releasePreparation()',ctx);await Promise.all([pendingEdit,coalescedEdit]);assert(ctx.BodyflipLab.state.playing,'same pending edit resumes');
 vm.runInContext('globalThis.preparationGate=new Promise(resolve=>globalThis.releasePreparation=resolve)',ctx);
 ids.get('attackReturnDuration').value='1';ids.get('attackReturnDuration').oninput();const cancelledResume=ids.get('attackReturnDuration').onchange();
 vm.runInContext('setPlaying(false);releasePreparation()',ctx);await cancelledResume;assert(!ctx.BodyflipLab.state.playing,'explicit Pause cancels automatic resume');
 vm.runInContext('F.prepare=savedPrepare',ctx);
 vm.runInContext('setPlaying(true)',ctx);ids.get('motion').value='kinematic';ids.get('motion').onchange();assert(ctx.BodyflipLab.state.playing,'motion option resumes');
 ids.get('trimLoop').checked=true;await ids.get('trimLoop').onchange();assert(ctx.BodyflipLab.state.playing,'loop option resumes');
 await ctx.BodyflipLab.loadAttack('slashL',1);assert(ctx.BodyflipLab.state.playing,'attack selection resumes');
 vm.runInContext('setPlaying(false)',ctx);
 assert.equal(worlds,1,'throw playback shares app world');assert(writes.every(p=>p==='/state'),'only mock save path');
 console.log(JSON.stringify({passed:true,scripts:scripts.length,worlds,frame:ctx.BodyflipLab.state.frame,projectileBodies:physics.projectileDiagnostics().bodies,retargetInputs:6,retargetDrags:6,referenceToggle:true,referenceMeshVertices:vm.runInContext('referenceMeshVertices',ctx),glRasterized:false,liveWrites:0}));
}finally{physics?.dispose();}
