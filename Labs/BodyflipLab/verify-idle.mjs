import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),S=require('./support.js'),I=require('./idle.js'),R=require('./recovery.js'),F=require('./flight.js');
const read=n=>fs.readFileSync(new URL(n,import.meta.url)),manifest=JSON.parse(read('data/manifest.json')),meta=JSON.parse(read('data/idle.json')),bytes=read('data/idle.bin'),loop=I.create(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),manifest),checks=[];
const check=(name,value)=>{assert(value,name);checks.push(name);};
check('Old Space saves migrate to Idle',C.sanitize({mode:'space'}).mode==='idle');
check('Idle preserves the existing frozen animation provenance',meta.sha256===manifest.sharedIdle.sha256&&meta.frames===301&&loop.duration===10);
const a=loop.sample(0),b=loop.sample(2);
check('Idle animates rather than holding one frame',Math.max(...a.points.map((p,i)=>R.length(R.sub(p,b.points[i]))))>.001);
check('Ten second loop repeats deterministically',JSON.stringify(loop.sample(1.25))===JSON.stringify(loop.sample(21.25)));
let maxGroundError=0,maxRootTravel=0,maxBoneError=0;
for(let frame=0;frame<600;frame++){
 const p=loop.sample(frame/60),raw=loop.rawAt(frame/60);
 const low=Math.min(...['L','R'].flatMap(side=>{const ankle=manifest.names.indexOf('foot_'+side.toLowerCase()),toe=manifest.names.indexOf('ball_'+side.toLowerCase());return S.footPoints(p,ankle,toe,side).map(v=>p.points[ankle][1]+v[1]);}));
 maxGroundError=Math.max(maxGroundError,Math.abs(low));maxRootTravel=Math.max(maxRootTravel,Math.hypot(p.points[0][0]-a.points[0][0],p.points[0][2]-a.points[0][2]));
 for(let i=1;i<manifest.names.length;i++){const j=manifest.parents[i];maxBoneError=Math.max(maxBoneError,Math.abs(R.length(R.sub(p.points[i],p.points[j]))-R.length(R.sub(raw.points[i],raw.points[j]))));}
}
check('Rendered shoe remains grounded throughout idle loop',maxGroundError<1e-8);
check('Idle root does not run or fall',maxRootTravel<1e-6);
check('Grounding preserves authored bone lengths',maxBoneError<1e-8);
const app=read('app.js').toString(),html=read('index.html').toString(),nodes=new Map();
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>JSON.parse(read(n)).clips).map(F.decodeJump);
const ctx={F,jumps,runCache:new Map(),run:null,seekRevision:0,seeking:false,playRevision:0,playing:false,document:{hidden:false},jumpTrack:{sync(){}},setPlaying(v){ctx.playing=v;ctx.playRevision++;},async post(path,data){if(path!=='/resume')throw Error('Idle must not request a gait bank');const r=await fetch('http://127.0.0.1:8876'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),result=await r.json();if(!r.ok)throw Error(result.error);return result;},settings:C.sanitize({mode:'idle',ramps:false,flipAngle:88,flipSpeed:720,twistSpeed:100}),idleLoop:loop,clip:null,idle:C.poseFromShared(manifest),parents:manifest.parents,names:manifest.names,simTime:1.25,attackTime:-1,flip:88,twist:23,flight:{},flightFrame:{},C,R,clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),physics:{step(p){ctx.result=p;},read(){return ctx.result;}},hit:false,bestMiss:Infinity,previousContact:null,runRevision:0,loadingRun:true,platformEditor:{refresh(){}},resetPhysics(){ctx.result=ctx.targetPose();},save(){},$:id=>{if(!nodes.has(id))nodes.set(id,{disabled:true});return nodes.get(id);}};
vm.createContext(ctx);
for(const [start,end] of [['function targetPose(){','function resetPhysics(){'],['async function prepareRun(','function total(){'],['function tick(','async function seek(']])vm.runInContext(app.slice(app.indexOf(start),app.indexOf(end)),ctx);
await ctx.prepareRun();
check('Idle uses the shared planner and seeds its landing NN without a gait-bank request',ctx.flight.events[0].status==='Push'&&!ctx.loadingRun&&!ctx.$('play').disabled&&!ctx.$('step').disabled);
check('Stationary start selects standing jump automatically',ctx.flight.segments[0].jumpStyle==='Stand');
ctx.tick();
check('Idle remains upright before jumping despite saved flip settings',ctx.flightFrame.phase==='IDLE'&&R.length(R.sub(R.sub(ctx.result.points[1],ctx.result.points[0]),R.sub(loop.sample(ctx.simTime).points[1],loop.sample(ctx.simTime).points[0])))<1e-9);
check('Idle tick advances the authored loop in place',ctx.simTime>0&&R.length(R.sub(R.sub(ctx.result.points[1],ctx.result.points[0]),R.sub(loop.sample(ctx.simTime).points[1],loop.sample(ctx.simTime).points[0])))<1e-9);

const delayed=C.sanitize({...ctx.settings,jumpEvents:[{id:'later',time:2,surface:'floor'}]}),later=F.sequence(loop.motion(),jumps,delayed,manifest.parents);
check('Moving a marker changes support start and keeps preceding idle',later.sample(1.5).phase==='IDLE'&&later.segments[0].supportStart===2&&later.events[0].status==='Push');
check('Jump leaves floor, falls, then resumes idle after landing',later.sample(2.3).root[1]>.2&&later.sample(2.7).phase.includes('FALL')&&later.sample(5).phase==='IDLE');
const repeated=F.sequence(loop.motion(),jumps,C.sanitize({...ctx.settings,jumpEvents:[{id:'first',time:.9,surface:'floor'},{id:'second',time:1.8,surface:'floor'}]}),manifest.parents);
check('Repeated idle-start markers use contact and push rules',repeated.events.length===2&&repeated.events.every(e=>e.status==='Push'));
const noJumps=F.sequence(loop.motion(.2),jumps,C.sanitize({...ctx.settings,jumpEvents:[]}),manifest.parents);
check('No markers leaves agent idling indefinitely',noJumps.sample(80).phase==='IDLE'&&noJumps.sample(80).root.every(Number.isFinite));
check('Phase changes idle starting pose',R.length(R.sub(noJumps.sample(0).pose.points[1],loop.sample(0).points[1]))>.001);
const firstSample=JSON.stringify(later.sample(2.3,45,20));later.sample(10);later.sample(.1);
check('Idle jump reverse seek is deterministic',JSON.stringify(later.sample(2.3,45,20))===firstSample);
check('Idle airborne flip remains available',R.length(R.sub(later.sample(2.3,45,20).pose.points[8],later.sample(2.3,0,0).pose.points[8]))>.01);
check('Jump, trim and options have no Idle visibility exception',!app.includes("hidden=settings.mode==='idle'")&&!read('jump-track.js').toString().includes("hidden=settings.mode==='idle'"));
check('Menu exposes Idle and removes Space sequence',html.includes('<option value="idle">Idle</option>')&&!html.includes('value="space"'));
fs.writeFileSync(new URL('idle-verification.json',import.meta.url),JSON.stringify({passed:checks.length,checks,maxGroundError,maxRootTravel,maxBoneError},null,2)+'\n');
console.log(JSON.stringify({passed:checks.length,maxGroundError,maxRootTravel,maxBoneError}));
