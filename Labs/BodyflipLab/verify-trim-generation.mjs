// Historical trim fixture retains its original loading; tier loading is tested separately.
// Offline: real jump/capsule/sequence, deterministic policy stub; no HTTP or NN.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js'),I=require('./idle.js');
const freshFlight=()=>{delete require.cache[require.resolve('./flight.js')];return require('./flight.js');};
const F=freshFlight(),read=n=>fs.readFileSync(new URL(n,import.meta.url));
const manifest=JSON.parse(read('data/manifest.json')),meta=JSON.parse(read('data/idle.json')),bytes=read('data/idle.bin');
const idle=I.create(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),manifest);
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>JSON.parse(read(n)).clips).map(F.decodeJump);
const checks=[],check=(label,ok)=>{assert(ok,label);checks.push(label);};
function policy(requests){return async request=>{
 requests.push(request);
 const pose=request.seeds[1],origin=request.roots[1],old=request.continuation?.ticks||0;
 return {names:request.names.slice(1),fps:30,duration:(request.frames-1)/30,
  roots:request.roots.slice(1,request.frames+1),
  poses:Array.from({length:request.frames},(_,i)=>({points:pose.points.slice(1).map(p=>R.add(p,R.sub(request.roots[i+1],origin))),axes:pose.axes.slice(1)})),
  continuation:{ticks:old+request.frames-1}};
};}
const settings=C.sanitize({loadYMs:100,loadFullMs:100,mode:'idle',ramps:false,surfaceIK:false,trimOut:.1,jumpEvents:[{id:'early',time:.2,surface:'floor'},{id:'later',time:3.5,surface:'floor'}]});
const requests=[],start=performance.now();
const short=await F.prepare(idle.motion(),jumps,settings,manifest.parents,undefined,policy(requests));
check('Initial preparation ends at active trim, not 12 seconds',short.preparedThrough===.1);
check('Markers beyond trim are not planned',short.events.length===0&&short.segments.length===0);
check('No future landing inference before trimmed first jump',requests.length===0);
const first=await short.extend(.8),segment=first.segments[0],prefix=JSON.stringify(first.sample(.5));
check('Extending prepares newly visible marker',first===short&&first.events.length===1&&first.preparedThrough===.8);
check('Prefix extension retains planned segment',segment&&first.segments[0]===segment);
await short.extend(2.8);
check('Future marker remains deferred',short.events.length===1);
check('Landing request is bounded by trim plus one policy frame',requests.length>0&&requests.every(q=>(q.frames-1)/30<=2.8-short.landings[0].time+1/30+1e-8));
const before=requests.length,oldFrames=requests[0].frames,oldPrefix=JSON.stringify(short.sample(2.6));
await short.extend(3.2);
check('Extending landing NN requests only new frames',requests.length===before+1&&requests.at(-1).continuation&&requests.at(-1).frames<oldFrames);
check('NN extension preserves previously generated pose',JSON.stringify(short.sample(2.6))===oldPrefix);
check('Original jump prefix remains byte-identical',JSON.stringify(short.sample(.5))===prefix&&short.segments[0]===segment);
const fullRequests=[],Full=freshFlight(),full=await Full.prepare(idle.motion(),jumps,{...settings,trimOut:3.2},manifest.parents,undefined,policy(fullRequests));
let error=0;for(let i=0;i<=192;i++){const a=short.sample(i/60),b=full.sample(i/60);for(let k=0;k<a.pose.points.length;k++)error=Math.max(error,R.length(R.sub(a.pose.points[k],b.pose.points[k])));}
check('Incremental extension matches full preparation over every frame',error<1e-8);
await short.extend(3.6);
check('Crossing later marker appends it exactly once',short.events.length===2&&short.segments.length===2&&short.events[1].id==='later');
check('Earlier segment survives append',short.segments[0]===segment);
const callCount=requests.length;await short.extend(1);check('Shortening prepared range does not regenerate',requests.length===callCount&&short.preparedThrough===3.6);
const space=await F.prepare(idle.motion(),jumps,{...settings,mode:'spaceGym'},manifest.parents,undefined,policy([]));
const spaceIdentity=await space.extend(.8);check('Space gym also defers markers and retains extension identity',spaceIdentity===space&&space.events.length===1&&space.preparedThrough===.8);
const actionRequests=[],actionSequence=await freshFlight().prepare(idle.motion(),jumps,{...settings,trimOut:2.8,jumpEvents:[
 {id:'push',time:.2,surface:'floor'},{id:'action',time:1.5,jumpPercent:0,surface:'floor'}]},manifest.parents,undefined,policy(actionRequests));
const action=actionSequence.segments.at(-1),actionRoot=action.carrier.state(2.8).root;
check('Zero-push actions preserve underlying capsule root state',actionRoot?.length===3&&actionRoot.every(Number.isFinite));
check('Zero-push action continues preparing inherited landing NN to trim end',actionRequests.length>0&&actionRequests.at(-1).frames>=48);
const handAfterAction=await freshFlight().prepare(idle.motion(),jumps,{...settings,trimOut:.8,jumpEvents:[
 {id:'action',time:.1,jumpPercent:0,surface:'floor'},{id:'hand',time:.2,pushWith:'handL',surface:'floor'}]},manifest.parents,undefined,policy([]));
check('Hand push after zero-push action has finite root and body',handAfterAction.sample(.6).pose.points.flat().every(Number.isFinite));
let delayPolicy=false,releasePolicy,policyWaiting=false;
const policyGate=new Promise(resolve=>{releasePolicy=resolve;}),delayedPolicy=policy([]);
const concurrent=await freshFlight().prepare(idle.motion(),jumps,{...settings,trimOut:2.8},manifest.parents,undefined,async request=>{
 if(delayPolicy){policyWaiting=true;await policyGate;}return delayedPolicy(request);
});
const heldPrefix=JSON.stringify(concurrent.sample(2.6));delayPolicy=true;
const extendingPolicy=concurrent.extend(3.2);await Promise.resolve();await Promise.resolve();
check('Existing prefix remains readable while new NN chunk is pending',policyWaiting&&JSON.stringify(concurrent.sample(2.6))===heldPrefix);
releasePolicy();await extendingPolicy;
check('Pending NN append completes without altering the displayed prefix',concurrent.preparedThrough===3.2&&JSON.stringify(concurrent.sample(2.6))===heldPrefix);
// Exercise the actual app seek/bracket functions with a delayed preparation.
const app=read('app.js').toString('latin1'),elements=new Map(),calls=[],placed=[];
let release;
const gate=new Promise(resolve=>{release=resolve;});
const mockFlight={preparedThrough:1,speed:0,async extend(end){calls.push(end);await gate;this.preparedThrough=end;return this;}};
const context=vm.createContext({flight:mockFlight,runRevision:1,extending:null,preparingRun:null,loadingRun:false,seekRevision:0,seeking:false,
 settings:{mode:'idle',motion:'kinematic',trimIn:0,trimOut:1},F:{eventsFor:()=>[]},jumpTrack:null,simTime:.7,hit:false,bestMiss:Infinity,
 previewRAF:null,previewTime:0,playing:false,playRevision:0,
 $:id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);},setPlaying(){},placeKinematic(time){placed.push(time);context.simTime=time;},
 clamp:(v,a,b)=>Math.max(a,Math.min(b,v)),syncTrim(){},save(){},fail(error){throw error;},cancelAnimationFrame(){},requestAnimationFrame(){return 1;}});
vm.runInContext(app.slice(app.indexOf('async function ensurePrepared('),app.indexOf('function animate(')),context);
vm.runInContext(app.slice(app.indexOf('function finishPreview('),app.indexOf('function placeKinematic(')),context);
const seekA=context.seek(2),seekB=context.seek(3);
check('Seek waits for new range without moving displayed pose early',context.simTime===.7&&context.loadingRun);
release();await Promise.all([seekA,seekB]);
check('Rapid extension coalesces requests and displays only latest seek',calls.join(',')==='2,3'&&placed.join(',')==='3'&&context.simTime===3);
context.finishPreview(.7);await Promise.resolve();await Promise.resolve();
check('Releasing trim preview restores original cursor in cached range',context.simTime===.7&&calls.length===2);
check('Extension releases playback controls',!context.loadingRun&&!elements.get('play').disabled&&!context.seeking);
context.settings.trimOut=4;context.previewRAF=1;context.finishPreview(.7);
await Promise.resolve();await Promise.resolve();await Promise.resolve();
check('Fast bracket release still prepares newly exposed end after cancelling preview RAF',calls.at(-1)===4&&mockFlight.preparedThrough===4&&context.simTime===.7);
let releaseEdit;context.preparingRun={promise:new Promise(resolve=>{releaseEdit=resolve;})};
const seekWhileEditing=context.seek(2);await Promise.resolve();
check('Seek during settings recompute waits for new prepared sequence',context.simTime===.7);
context.preparingRun=null;releaseEdit();await seekWhileEditing;
check('Queued seek resumes after settings preparation',context.simTime===2&&!context.seeking);
let releaseStaleEdit;context.preparingRun={promise:new Promise(resolve=>{releaseStaleEdit=resolve;})};
const staleSeek=context.seek(12),callsBeforeEdit=calls.length;
context.runRevision++;context.seekRevision++;
context.flight={...mockFlight,preparedThrough:2.55};context.preparingRun=null;releaseStaleEdit();await staleSeek;
check('Cancelled seek cannot extend new settings generation past its trim end',calls.length===callsBeforeEdit&&context.flight.preparedThrough===2.55&&context.simTime===2);
let releaseStalePreview;context.preparingRun={promise:new Promise(resolve=>{releaseStalePreview=resolve;})};
context.settings.trimOut=12;context.finishPreview(2);
context.runRevision++;context.seekRevision++;context.settings.trimOut=2.55;context.preparingRun=null;releaseStalePreview();
await Promise.resolve();await Promise.resolve();await Promise.resolve();
check('Cancelled bracket finish cannot extend replacement settings sequence',calls.length===callsBeforeEdit&&context.flight.preparedThrough===2.55);
let savedSnapshot,reloaded=false;
context.playing=true;context.saveTimer=null;context.clearTimeout=()=>{};
context.stored=()=>({playback:{time:context.simTime,playing:context.playing}});
context.setPlaying=value=>{context.playing=value;};
context.persist=async snapshot=>{savedSnapshot=snapshot;};context.location={reload(){reloaded=true;}};
vm.runInContext(app.slice(app.indexOf('async function refreshLab('),app.indexOf('function save(')),context);
const revisionBeforeRefresh=context.runRevision;await context.refreshLab();
check('Refresh captures playback before pausing and cancels obsolete background preparation',savedSnapshot.playback.time===2&&savedSnapshot.playback.playing&&context.runRevision===revisionBeforeRefresh+1&&reloaded);
console.log(JSON.stringify({checks,elapsedMs:performance.now()-start,requests:requests.map(q=>({frames:q.frames,continuation:!!q.continuation})),maxPrefixError:error},null,2));
