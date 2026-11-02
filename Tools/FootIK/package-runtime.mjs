// Build-time packaging only. Gameplay executes these exact lab modules in V8.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import footCorners from './foot-corners.cjs';
const root=path.resolve('Labs/FootIKLab'),out=path.resolve('Content/FootIKLab'),sources=new Map(),seams=[];
function gather(file){file=path.resolve(file);if(sources.has(file))return;const text=fs.readFileSync(file,'utf8').replaceAll('\r\n','\n');sources.set(file,text);for(const m of text.matchAll(/require\(['"]([^'"]+)['"]\)/g))if(m[1].startsWith('.')&&fs.existsSync(path.resolve(path.dirname(file),m[1])))gather(path.resolve(path.dirname(file),m[1]));}
for(const file of ['footik.js','handoff.js','surface.js','surface-coupling.js','slide-joints.js','slide-entry.js','slide-arms.js'])gather(path.join(root,file));
gather(path.resolve('Tools/FootIK/live-stair-planner.cjs'));
gather(path.resolve('Tools/FootIK/live-join.cjs'));
gather(path.resolve('Tools/FootIK/live-exit.cjs'));
gather(path.resolve('Tools/FootIK/native-arm-fit.cjs'));
gather(path.resolve('Tools/FootIK/native-entry-fit.cjs'));
gather(path.resolve('Tools/FootIK/native-leg-contact.cjs'));
const kernelContractPath='Tools/FootIK/native-kernel-contract.json',kernelContract=JSON.parse(fs.readFileSync(kernelContractPath,'utf8'));
if(kernelContract.schema!=='footik-native-kernel-contract-v1')throw Error('Unsupported native kernel dependency contract');
for(const [kernel,dependencies] of Object.entries(kernelContract.dependencies))for(const [name,expected] of Object.entries(dependencies)){const source=sources.get(path.join(root,name));if(source===undefined||crypto.createHash('sha256').update(source).digest('hex')!==expected)throw Error('Native '+kernel+' dependency changed: '+name+'. Revalidate its native kernel and update native-kernel-contract.json before packaging; stale native math must not run.');}
function once(text,from,to,label){if(text.split(from).length!==2)throw Error('Canonical FootIK host seam changed: '+label);seams.push(label);return text.replace(from,to);}
function adapt(file,text){
 if(path.basename(file)==='support.js'){
  text=once(text,'const corners=(c,f,s,u,d)=>[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>add(add(add(c,mul(f,x*d[0]/2)),mul(s,y*d[1]/2)),mul(u,z*d[2]/2)))));',
   'const corners='+footCorners.corners.toString()+';','allocation-free intermediate foot corners');
 }
 if(path.basename(file)==='footik.js'){
  if(!text.includes('if(host.initialCheckpoint)return host.initialCheckpoint('))throw Error('Missing optional actual-history checkpoint seam');
  seams.push('opt-in boundary checkpoint preserves contact limits and shared weight order');
  text=once(text,'function reachable(target,hip,reach,offsets,terrain){','function reachable(target,hip,reach,offsets,terrain){\n if(terrain.reachable){const native=terrain.reachable(target,hip,reach,offsets);if(native)return native;}','complete native12-pass reach with canonical fallback');
  const search=`   let limit=1;
   for(let n=1;n<=16;n++)if(!clear(n/16)){
    let lo=(n-1)/16,hi=n/16;
    for(let k=0;k<9;k++){const mid=(lo+hi)/2;if(clear(mid))lo=mid;else hi=mid;}
    limit=lo;break;
   }
`;
  text=once(text,search,`   let limit=terrain.rotationClearance?terrain.rotationClearance(planned[i].targets[side],base[i],l,original,natural,planned[i].targets[side][1]+1e-7,1,0):null;
   if(limit===null){
${search.replace('   let limit=1;','   limit=1;')}   }
`,'complete native ankle clearance search with canonical fallback');
  text=once(text,'    if(!clear(amount)&&clear(0)){','    const nativeAmount=terrain.rotationClearance?terrain.rotationClearance(target,base[i],l,original,natural,target[1]+1e-7,amount,1):null;\n    if(nativeAmount!==null)amount=nativeAmount;else if(!clear(amount)&&clear(0)){','complete native anticipated ankle clearance with canonical fallback');
 }
 if(path.basename(file)==='slide-entry.js'){
  text=once(text,"'use strict';","'use strict';const NativeEntryFit=require('./native-entry-fit.cjs');",'native entry wire contract');
  const start=text.indexOf(' let obstacleWeight=1000;'),end=text.indexOf(' inspect?.({nodes,evaluateGeometry,correct,project});',start);
  if(start<0||end<0)throw Error('Canonical entry search boundary changed');
  const original=text.slice(start,end);
  text=once(text,original," if(!NativeEntryFit.solve({nodes,quality,hip,knee,foot:joints.joints[l.foot],leg:l,surfaces})){\n"+original+" }\n",'complete native entry search with canonical fallback');
 }
 if(path.basename(file)==='slide-arms.js'){
  text=once(text,"'use strict';","'use strict';const NativeArmFit=require('./native-arm-fit.cjs');",'native brace wire contract');
  const start=text.indexOf('   let best=fit(1);'),end=text.indexOf('   // Commit history only after choosing a fit;',start);
  if(start<0||end<0)throw Error('Canonical brace search boundary changed');
  const original=text.slice(start,end),fallback=original.replace('let best=fit(1);','best=fit(1);');
  const native="   let best;\n   if(typeof globalThis.__footikBraceFit==='function')best=NativeArmFit.unpack(JSON.parse(globalThis.__footikBraceFit(...NativeArmFit.pack({pose,a,parents,joints,nearest,requestedPoint,n,wallUp,shoulderOut,reach,handQ}))),a);\n   else{\n"+fallback+"   }\n";
  text=once(text,original,native,'complete native brace search with canonical fallback');
 }
 if(['live-stair-planner.cjs','live-terrain.cjs','stair-boundary.cjs','live-join.cjs','live-exit.cjs','native-leg-contact.cjs'].includes(path.basename(file)))text=text.replaceAll("require('../../Labs/FootIKLab/","require('./");
 if(path.basename(file)==='live-stair-planner.cjs'){
  text=once(text,'async function predict(update){','function predict(update){','synchronous live prediction');
  text=once(text,'const result=await infer(request);','const result=infer(request);','native live policy');
  text=once(text,'async function plan(update={}){','function plan(update={}){','synchronous live plan');
  text=once(text,'update.roots?await predict(update):source','update.roots?predict(update):source','native live forecast');
  text=once(text,'const reply=await infer(request.request);','const reply=infer(request.request);','native live handoff');
 }
 if(path.basename(file)==='handoff.js'){
  text=once(text,'async function prepare(run,settings,resume,cancelled=()=>false){','function prepare(run,settings,resume,cancelled=()=>false){','synchronous terrain handoff');
  text=once(text,'const response=await resume(plan.request);','const response=resume(plan.request);','native multi-frame continuation');
 }
 if(path.basename(file)==='surface.js'){
  text=once(text,"'use strict';","'use strict';const NativeLegContact=require('./native-leg-contact.cjs');",'native leg contact wire contract');
  const start=text.indexOf('   const contactValid=p=>{'),end=text.indexOf('   targets.push({side,l,target:goal.points[l.foot],rotation:{footQ:goal.q[l.foot],toeQ:goal.q[l.toe]}});',start);
  if(start<0||end<0)throw Error('Canonical leg contact boundary changed');
  const original=text.slice(start,end);
  text=once(text,original,"   const nativeLeg=NativeLegContact.solve({goal,l,parents,joints,rotation,point,wantedAxis,wantedPole,e,side,targetShift,previousPole,dt,plane,terrain});\n   if(nativeLeg)goal=nativeLeg;else{\n"+original+"   }\n",'complete native leg contact with canonical fallback');
  // Host seams only: the algorithm continues to own contacts, constraints,
  // dynamics and slide transitions. Existing browser calls take identical paths.
  text=once(text,'enabled=true,metrics=createMetrics(),events=[]},saved=null)','enabled=true,metrics=createMetrics(),events=[],controller=null},saved=null)','root controller input');
  text=once(text,'let command=mul(direction,speed);','let command=controller?controller(time,actualNormal):mul(direction,speed);','live root drive');
  text=once(text,"const hasFloor=terrain.surfaces.some(x=>x.id==='entry');","const hasFloor=terrain.surfaces.some(x=>x.id==='entry');\n  if(terrain.hostWorld&&!terrain.surfaces.length)lastSupportTime=-Infinity;\n  if(terrain.hostWorld&&slide&&!terrain.surfaces.some(x=>x.id===slide.surface)){events.push({frame:time*60,type:'slide-exit',time,velocity:velocity.slice(),reason:'surface-removed'});slide=null;lastSupportTime=-Infinity;exited=true;}",'live removed surface releases support');
  text=once(text,"if(s.approach==='parallel'){const contour", "if(!controller&&s.approach==='parallel'){const contour",'live controller owns lateral input');
  text=once(text,'createRootMotion({s,terrain,height,speed,gravity,enabled},snapshot())','createRootMotion({s,terrain,height,speed,gravity,enabled,controller},snapshot())','root forecast controller');
  text=once(text,'motionSurface=terrain.allSurfaces.find(x=>x.id===saved.motionSurface)||terrain.floor','motionSurface=terrain.allSurfaces.find(x=>x.id===saved.motionSurface)||terrain.resolveRootSurface?.(saved.motionSurface)||terrain.floor','retain noncolliding root reference after removal');
  text=once(text,'count=Math.round(duration*fps)+1,{names,parents}=run','count=experiment.live?Infinity:Math.round(duration*fps)+1,{names,parents}=run','unbounded incremental host');
  text=once(text,'const terrain=createTerrain(s,Math.max(28,speed*duration+.5*Math.abs(gravity)*duration**2+2*height))','const terrain=experiment.terrain||createTerrain(s,Math.max(28,speed*duration+.5*Math.abs(gravity)*duration**2+2*height))','host terrain');
  text=once(text,'const motion=createRootMotion({s,terrain,height,speed,gravity,enabled,metrics,events});','const motion=experiment.motion?experiment.motion({s,terrain,height,speed,gravity,enabled,metrics,events}):createRootMotion({s,terrain,height,speed,gravity,enabled,metrics,events});','host root motion');
  text=once(text,'const frames=[];let lastSupports=[];','const frames=experiment.frames||[];let lastSupports=[];','bounded live frame history');
  text=once(text,'const time=i/fps,context=motion.begin(time)','const time=(experiment.startTime||0)+i/fps,context=motion.begin(time)','external surface clock origin');
  text=once(text,'heading:K.rootHeading(run,time,s,speed),headingAt:t=>K.rootHeading(run,t,s,speed)','heading:experiment.headingAt?experiment.headingAt(time):K.rootHeading(run,time,s,speed),headingAt:t=>experiment.headingAt?experiment.headingAt(t):K.rootHeading(run,t,s,speed)','live slide heading window');
  text=once(text,'const api={settings,createTerrain,prepare,simulate,createFeet','const api={createRootMotion,createSlidePose,createMetrics,settings,createTerrain,prepare,simulate,createFeet','expose canonical host factories');
 }
 if(path.basename(file)==='surface-coupling.js'){
  // Native NN callbacks are synchronous. Remove only Promise orchestration;
  // preserve the same requests, policy boundaries and interpolation arithmetic.
  text=once(text,'function createSession(run,input,infer){','function createSession(run,input,infer,host={}){','coupling host inputs');
  text=once(text,'F.simulate(run,s,{interactive:true,checkpoints:true,onModel:value=>{model=value;}})','F.simulate(run,s,{...host,interactive:true,checkpoints:true,onModel:value=>{model=value;}})','coupling live solver');
  text=once(text,'queue=Promise.resolve();','queue=null;','native synchronous queue');
  text=once(text,'lastPolicyIndex=-1,queue=null;','lastPolicyIndex=-1,queue=null,resumedHistory=null;','retain resume policy pair');
  text=once(text,'roots=[],poses=[],contexts=[],steps=[],windows=[]','roots=host.live?{}:[],poses=host.live?{}:[],contexts=host.live?{}:[],steps=host.steps||[],windows=host.windows||[]','bounded live policy history');
  text=once(text,' function resumePose(source,at,originalTime,position){',' if(host.initialPair){roots[-4]=host.initialPair.previous.points[0];poses[-4]=host.initialPair.previous;}\n function resumePose(source,at,originalTime,position){','measured live policy history');
  text=once(text,'function resumePose(source,at,originalTime,position){','function resumePose(source,at,originalTime,position,originalYaw){','live resume heading source');
  text=once(text,'K.commandYaw(s,at,speed)-K.commandYaw(s,originalTime,speed)','(host.yawAt?host.yawAt(at):K.commandYaw(s,at,speed))-(originalYaw??K.commandYaw(s,originalTime,speed))','live resume heading delta');
  text=once(text,'slideSource||={pose:p,previous:poses[Math.max(0,i-4)]||p,time}','slideSource||={pose:p,previous:poses[Math.max(0,i-4)]||p,time,...(host.yawAt?{yaw:host.yawAt(time),previousYaw:host.yawAt(time-1/30)}:{})}','retain slide-entry heading');
  text=once(text,'resumePose(resumeSource.pose,time,resumeSource.time,virtual)','resumePose(resumeSource.pose,time,resumeSource.time,virtual,resumeSource.yaw)','resume current heading');
  text=once(text,'resumePose(resumeSource.previous,time-1/30,resumeSource.time-1/30,roots[i-4])','resumePose(resumeSource.previous,time-1/30,resumeSource.time-1/30,roots[i-4],resumeSource.previousYaw)','resume previous heading');
  text=once(text,'async function consumePolicy(){','function consumePolicy(){','synchronous policy call');
  text=once(text,'result=await infer(request,steps.length);','result=infer(request,steps.length);','native policy reply');
  text=once(text,'const target=pose(result.pose);segment=pair(p,target,run.parents);','if(request.reset)resumedHistory={i,previous:pose(request.seeds[0]),current:pose(request.seeds[1])};\n  const target=pose(result.pose);segment=pair(p,target,run.parents);','retain exact reset seed history');
  text=once(text,'async function advance(endTime,cancelled){','function advance(endTime,cancelled){','synchronous advancement');
  text=once(text,'  await consumePolicy();','  consumePolicy();','pending policy boundary');
  text=once(text,'if(i<last)await consumePolicy();','if(i<last)consumePolicy();','policy boundary');
  text=once(text,'Math.min(Math.round(model.duration*120),Math.max(0,Math.ceil(+endTime*120-1e-8)))','Math.min(host.live?Infinity:Math.round(model.duration*120),Math.max(0,Math.ceil(+endTime*120-1e-8)))','unbounded coupling interval');
  text=once(text,'time<model.duration-1e-8&&lastPolicyIndex!==i','(host.live||time<model.duration-1e-8)&&lastPolicyIndex!==i','unbounded policy clock');
  text=once(text,'!c.slide&&i>=4&&i%4===0','!c.slide&&(i>=4||host.initialPair&&i===0)&&i%4===0','measured current policy boundary');
  text=once(text,'const virtual=i?add(roots[i-1],transport(contexts[i-1],c)):[0,0,0];','const virtual=i?add(roots[i-1],transport(contexts[i-1],c)):(host.initialPair?.current.points[0]||[0,0,0]);','measured virtual origin');
  text=once(text,'rootYawDegrees:path.map((_,k)=>K.commandYaw(s,time+(k-1)/30,speed))','rootYawDegrees:path.map((_,k)=>host.yawAt?host.yawAt(time+(k-1)/30):K.commandYaw(s,time+(k-1)/30,speed))','actual future root yaw');
  text=once(text,'const request={gait:s.gait,policy:', 'const request={gait:host.gaitAt?host.gaitAt():s.gait,policy:', 'live gait request');
  text=once(text,'F.gaitIntent(p,l,velocity,speed,active[side])','F.gaitIntent(p,l,velocity,host.speedAt?host.speedAt(time):speed,active[side])','live gait speed');
  text=once(text,'let p=anchored(segment?segment((i-segmentStart)/4):K.at(run,time),virtual);','let p=anchored(segment?segment((i-segmentStart)/4):K.at(run,time),virtual);\n  if(host.initialPair&&i===0)p=host.initialPair.current;\n  if(host.sourceAt)p=host.sourceAt(time,p,virtual)||p;','optional measured pose source');
  text=once(text,'const velocity=lastPose?mul(sub(p.points[l.foot],lastPose.points[l.foot]),120):','const velocity=lastPose?mul(sub(p.points[l.foot],lastPose.points[l.foot]),120):host.initialPair?mul(sub(p.points[l.foot],host.initialPair.previous.points[l.foot]),30):','measured initial gait velocity');
  text=once(text,'poses[i]=p;lastPose=p;next=sim.next({pose:p,legs,stance:active.slice(),untilPlant});','poses[i]=p;lastPose=p;next=sim.next({pose:p,legs,stance:active.slice(),untilPlant});\n   host.onFrame?.({i,time,virtual,context:c,source:p,frame:model.frames.at(-1)});\n   if(host.live&&i>8){delete roots[i-9];delete poses[i-9];delete contexts[i-9];}','retire expired live history');
  text=once(text,'extend(endTime,cancelled=()=>false){const task=queue.then(()=>advance(endTime,cancelled));queue=task.catch(()=>{});return task;}','extend(endTime,cancelled=()=>false){return advance(endTime,cancelled);}','native serial extend');
  const handoff=`function policyHandoff(){
  const i=model.frames.length-1,c=contexts[i];if(!c)throw Error('No accepted policy frame');
  const virtual=roots[i],time=c.time,paused=slideSource||resumeSource;
  let current=poses[i],previous=poses[i-4],previousVirtual=roots[i-4],previousRoot=contexts[i-4]?.base;
  if(i<4&&host.initialPair){previous=pair(host.initialPair.previous,host.initialPair.current,run.parents)(i/4);previousVirtual=previous.points[0];const before=host.initialPreviousRoot||sub(contexts[0].base,mul(contexts[0].velocity,1/30));previousRoot=add(before,mul(sub(contexts[0].base,before),i/4));}
  if(resumedHistory&&i>=resumedHistory.i&&i<resumedHistory.i+4)previous=pair(resumedHistory.previous,resumedHistory.current,run.parents)((i-resumedHistory.i)/4);
  if(!previous||!previousVirtual||!previousRoot)throw Error('Actual policy history is unavailable');
  if(paused){current=resumePose(paused.pose,time,paused.time,virtual,paused.yaw);previous=resumePose(paused.previous,time-1/30,paused.time-1/30,previousVirtual,paused.previousYaw);}
  return {tick:i,time,previous,current,root:c.base,previousRoot,velocity:c.velocity,normal:c.normal,bodyRotation:c.rootQ,sliding:!!paused,yaw:host.yawAt?host.yawAt(time):K.commandYaw(s,time,speed),previousYaw:host.yawAt?host.yawAt(time-1/30):K.commandYaw(s,time-1/30,speed)};
 }
 `;
  text=once(text,' return {model,steps,get generatedThrough()', ' '+handoff+'return {policyHandoff,model,steps,get generatedThrough()', 'read-only canonical policy handoff');
 }
 return text;
}
const id=file=>file.startsWith(path.resolve('Tools/FootIK')+path.sep)?path.basename(file):path.relative(root,file).replaceAll('\\','/');
const factories=[...sources].map(([file,text])=>JSON.stringify(id(file))+':function(module,exports,require){\n'+adapt(file,text)+'\n}');
const runtime=`/* Generated from canonical lab modules; see Receipt.json hostSeams. */
globalThis.structuredClone ||= function clone(value){if(value===null||typeof value!=='object')return value;if(Array.isArray(value))return value.map(clone);const out={};for(const key of Object.keys(value))out[key]=clone(value[key]);return out;};
globalThis.performance ||= {now:()=>Date.now()};
globalThis.FootIKRequire=(function(){const f={${factories.join(',\n')}},cache={};function load(id){if(cache[id])return cache[id].exports;if(!f[id])throw Error('Unknown Foot IK module '+id);const m={exports:{}};cache[id]=m;f[id](m,m.exports,name=>{const parts=id.split('/');parts.pop();for(const p of name.split('/')){if(p==='..')parts.pop();else if(p!=='.')parts.push(p);}return load(parts.join('/'));});return m.exports;}return load;})();\n`;
fs.mkdirSync(out,{recursive:true});
const compiler=process.env.FOOTIK_ESBUILD||path.resolve('Saved/Diagnostics/BodyflipPort20261030/esbuild/package/esbuild.exe');
if(!fs.existsSync(compiler))throw Error('Set FOOTIK_ESBUILD to pinned esbuild 0.25.12 (build-time only).');
const version=spawnSync(compiler,['--version'],{encoding:'utf8'}).stdout.trim();if(version!=='0.25.12')throw Error('Expected esbuild 0.25.12, got '+version);
const transformed=spawnSync(compiler,['--target=es2017','--supported:exponent-operator=false'],{input:runtime+fs.readFileSync('Tools/FootIK/runtime-adapter.js','utf8'),encoding:'utf8',maxBuffer:16*1024*1024});
if(transformed.status!==0)throw Error(transformed.stderr);
const polyfills=fs.readFileSync('Tools/FootIK/runtime-polyfills.js','utf8'),math=fs.readFileSync('Tools/FootIK/v8-trig.js','utf8');fs.writeFileSync(path.join(out,'Runtime.js'),polyfills+'\n'+math+'\n'+transformed.stdout);
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const hostHelpers=Object.fromEntries(['Tools/FootIK/foot-corners.cjs'].map(p=>[p,hash(fs.readFileSync(p))]));
const nativeMathFiles=['Tools/FootIK/v8-math/src/base/ieee754.cc','Tools/FootIK/v8-math/src/base/ieee754.h','Tools/FootIK/v8-math/src/base/macros.h','Tools/FootIK/v8-math/src/base/overflowing-math.h','Tools/FootIK/v8-math/src/base/build_config.h','Tools/FootIK/v8-math/src/base/base-export.h','Source/ProphecyFootIKMath/ProphecyFootIKMath.Build.cs','Source/ProphecyFootIKMath/Private/ProphecyFootIKMath.cpp','Source/ProphecyFootIKMath/Private/ProphecyFootIKArmKernel.cpp','Source/ProphecyFootIKMath/Public/ProphecyFootIKArmKernel.h','Source/ProphecyFootIKMath/Private/ProphecyFootIKEntryKernel.cpp','Source/ProphecyFootIKMath/Public/ProphecyFootIKEntryKernel.h','Source/ProphecyFootIKMath/Private/ProphecyFootIKLegKernel.cpp','Source/ProphecyFootIKMath/Public/ProphecyFootIKLegKernel.h','Source/ProphecyFootIKMath/Private/ProphecyFootIKFloorKernel.cpp','Source/ProphecyFootIKMath/Public/ProphecyFootIKFloorKernel.h'];
const notices='Foot IK native math compatibility: V8 13.6.233.17.\n\n'+fs.readFileSync('Tools/FootIK/v8-math/LICENSE','utf8')+'\n\n'+fs.readFileSync(nativeMathFiles[0],'utf8').split('\n').slice(0,14).join('\n');
fs.writeFileSync(path.join(out,'ThirdPartyNotices.txt'),notices);
const receipt={schema:'footik-runtime-v1',engine:'ClearScript.V8.Native.win-x64 7.5.1.1',compiler:{name:'esbuild',version,target:'es2017',lowerExponentOperator:true},hostSeams:seams,sources:Object.fromEntries([...sources].map(([p,t])=>[id(p),hash(t)])),adapter:hash(fs.readFileSync('Tools/FootIK/runtime-adapter.js')),polyfills:hash(polyfills),deterministicTrigWasm:hash(math),nativeKernels:{contract:hash(fs.readFileSync(kernelContractPath)),dependencies:kernelContract.dependencies},nativeMath:{v8:'13.6.233.17',sources:Object.fromEntries(nativeMathFiles.map(p=>[p,hash(fs.readFileSync(p))])),notices:hash(notices)},runtime:hash(fs.readFileSync(path.join(out,'Runtime.js')))};
receipt.hostHelpers=hostHelpers;
fs.writeFileSync(path.join(out,'Receipt.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify({modules:sources.size,hostSeams:seams.length,runtimeBytes:fs.statSync(path.join(out,'Runtime.js')).size}));
