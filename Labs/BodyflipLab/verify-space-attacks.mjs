import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),R=require('./recovery.js'),A=require('./jump-attack.js'),G=require('./space-gym.js'),I=require('./idle.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),buffer=n=>{const b=fs.readFileSync(new URL(n,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),parents=m.parents,names=m.names,reference=C.poseFromShared(m),run=I.create(read('data/idle.json'),buffer('data/idle.bin'),m).motion();
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),catalog=new Map(read('data/vanilla.json').clips.map(meta=>[meta.name,C.decode(meta,buffer(meta.file),names,parents)]));
const checks=[],check=(name,value)=>{assert(value,name);checks.push(name);},distance=(a,b)=>R.length(R.sub(a,b)),poseError=(a,b)=>Math.max(...a.points.map((p,i)=>distance(p,b.points[i]))),qe=(a,b)=>1-Math.abs(R.dot(a,b));
const started=performance.now(),event={id:'a',time:.5,surface:'auto',jumpPercent:0,flip:360,twist:180,attack:'slashLD',attackDelay:.12,pose:'pose2'};
const seq=await F.prepare(run,jumps,{mode:'spaceGym',jumpEvents:[event]},parents,reference,()=>{throw Error('Space requested NN');},()=>false,catalog);
check('Space has no ground and no landing requests',seq.surfaces.length===0&&seq.landings.length===0);
check('Zero push still starts turn, pose and attack',seq.sample(1).jumpMotion.flip!==0&&seq.sample(1).jumpMotion.poseWeight>0&&!!seq.sample(.8).attack);
check('Zero push root remains fixed for entire sequence',[0,.5,1,2,10].every(t=>distance(seq.sample(t).root,[0,1.2,0])<1e-12));
const drift=F.sequence(run,jumps,{mode:'spaceGym',jumpEvents:[{...event,flip:0,twist:0,pose:'none',attack:'none',jumpPercent:100}]},parents,reference,null,catalog);
check('Nonzero push drifts at constant speed without gravity',distance(R.sub(drift.sample(3).root,drift.sample(2).root),R.sub(drift.sample(2).root,drift.sample(1).root))<1e-10&&drift.sample(2).vy>0);
const half=F.sequence(run,jumps,{mode:'spaceGym',jumpEvents:[{...event,attack:'none',jumpPercent:25}]},parents,reference,null,catalog);
check('25 percent height uses half impulse speed',Math.abs(half.sample(2).vy/drift.sample(2).vy-.5)<1e-12);
const baseline=t=>{const pose=run.sample(t);return {pose,root:pose.points[0],phase:'SPACE'};};
const upper=A.bones(names,parents),lower=names.map((_,i)=>i).filter(i=>!upper.includes(i));
for(const [name,clip] of catalog){
 const segment=G.action({time:.5},baseline),e={attack:name,attackDelay:.1},attack=A.create(e,segment,catalog,names,parents,{...C.defaults,pelvisAttackCompensation:0});
 if(attack.fullBodyKick){
  const active=names.indexOf(C.effector(name)),hit=attack.sample(attack.hitTime).pose;
  check(name+' uses full-body viewer motion',attack.fullBodyKick&&distance(hit.points[active],baseline(attack.hitTime).pose.points[active])>.1);
  check(name+' enters and exits without snapping',poseError(attack.sample(attack.start).pose,baseline(attack.start).pose)<1e-9&&poseError(attack.sample(attack.returnEnd).pose,baseline(attack.returnEnd).pose)<1e-9);
  check(name+' retains native source timing',Math.abs(attack.sourceFrame(attack.duration+1/60)-clip.meta.phases.armed-clip.meta.fps/60)<1e-9);
  continue;
 }
 check(name+' selects a pre-Armed frame',attack.match>=0&&attack.match<=clip.meta.phases.armed);
 check(name+' delay and entry are continuous',poseError(attack.sample(attack.start).pose,baseline(attack.start).pose)<1e-9&&poseError(attack.sample(attack.start+1e-7).pose,baseline(attack.start+1e-7).pose)<1e-8);
 let lowerError=0,vanillaError=0;
 for(let t=attack.start;t<=attack.end+.25;t+=1/120){const a=attack.sample(t).pose,b=baseline(t).pose;for(const i of lower)lowerError=Math.max(lowerError,distance(a.points[i],b.points[i]),qe(a.q[i],b.q[i]));if(t>=attack.start+attack.duration&&t<attack.end){const local=R.localize(a.points,a.q,parents),target=A.attackAt(clip,attack.sourceFrame(t-attack.start),names,parents);for(const i of upper)vanillaError=Math.max(vanillaError,qe(local.q[i],target.q[i]));}}
 check(name+' leaves root pelvis and both legs unchanged',lowerError<1e-9);
 check(name+' plays vanilla at native speed through full follow-through',vanillaError<1e-9&&Math.abs(attack.sourceFrame(attack.duration+1/60)-clip.meta.phases.armed-clip.meta.fps/60)<1e-9);
 check(name+' returns to continuing base pose',poseError(attack.sample(attack.end+.25).pose,baseline(attack.end+.25).pose)<1e-10);
}
const paired=F.sequence(run,jumps,{mode:'spaceGym',jumpEvents:[event,{...event,id:'b',time:.8,attack:'jabL',attackDelay:0}]},parents,reference,null,catalog);
check('Overlapping attacks enter from the displayed upper pose',poseError(paired.sample(.8).pose,seq.sample(.8).pose)<1e-9);
const snapshot=JSON.stringify(paired.sample(.95));paired.sample(10);paired.sample(0);check('Reverse seek is deterministic',snapshot===JSON.stringify(paired.sample(.95)));
const floor={id:'floor',position:[0,-.2,0],size:[20,.4,40],rotation:[0,0,0,1]},heights=[];
for(const percent of [0,25,100,200]){
 const plan=F.sequence(run,jumps,{mode:'idle',surfaceIK:false,platforms:[floor],ramps:false,loadMs:0,jumpEvents:[{id:'a',time:.5,surface:'floor',jumpPercent:percent,attack:'jabR'}]},parents,reference,null,catalog);
 heights.push(Math.max(...Array.from({length:180},(_,i)=>plan.sample(.5+i/60).root[1]))-plan.sample(.5).root[1]);
 check('Ground '+percent+' percent plays its attack',Array.from({length:120},(_,i)=>plan.sample(.5+i/60).attack).some(Boolean));
}
check('Ground jump height scales; zero has only body-clearance correction',heights[0]>=0&&heights[0]<.06&&heights[1]>0&&Math.abs(heights[1]/heights[2]-.25)<.02&&Math.abs(heights[3]/heights[2]-2)<.02);
check('Scene round-trip retains marker fields',JSON.stringify(C.sanitize(JSON.parse(JSON.stringify(C.sanitize({mode:'spaceGym',jumpEvents:[event]})))) .jumpEvents[0])===JSON.stringify(C.sanitize({mode:'spaceGym',jumpEvents:[event]}).jumpEvents[0]));
// This is the maximum 32-marker overlap, including continuous 240 Hz spin,
// inertia and legal-pose tracking. Allow GC from the preceding full corpus.
const busyEvents=Array.from({length:32},(_,i)=>({...event,id:'b'+i,time:.5+i/60,attackDelay:0})),busyStart=performance.now();
const busy=F.sequence(run,jumps,{mode:'spaceGym',jumpEvents:busyEvents},parents,reference,null,catalog);busy.sample(1.05);busy.sample(1.1);
const busyMs=performance.now()-busyStart;
check('32 overlapping markers remain bounded ('+Math.round(busyMs)+' ms)',busyMs<12000);
if(process.argv.includes('--landing')){
 const e={id:'land',time:.5,surface:'floor'},settings={mode:'idle',surfaceIK:false,platforms:[floor],ramps:false,jumpEvents:[e]};
 const base=F.sequence(run,jumps,settings,parents,reference),land=base.landings[0].time;
 const attackEvent={...e,attack:'slashLD',attackDelay:Math.max(0,land-base.segments[0].airStart-.15)};
 let requests=0;
 const prepared=await F.prepare(run,jumps,{...settings,jumpEvents:[attackEvent]},parents,reference,async request=>{requests++;const r=await fetch('http://127.0.0.1:8876/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});assert(r.ok);return r.json();},()=>false,catalog);
 const time=prepared.landings[0].time,frame=prepared.sample(time),source=prepared.segments[0].sample(time),shift=R.sub(frame.root,source.root);
 check('Landing actually occurs during the scheduled attack',!!source.attack&&requests>0&&prepared.sample(time+.1).returnedToLocomotion);
 check('NN landing takes the displayed attacked upper pose',poseError(frame.pose,{...source.pose,points:source.pose.points.map(p=>R.add(p,shift))})<1e-5);
 check('Attack-to-NN landing has no pose snap',poseError(prepared.sample(time-1e-7).pose,frame.pose)<1e-5);
}
const receipt={checks:checks.length,elapsedMs:performance.now()-started,busyMs,heights,checksPassed:checks};fs.writeFileSync(new URL('space-attacks-verification.json',import.meta.url),JSON.stringify(receipt,null,2));console.log(JSON.stringify({checks:checks.length,elapsedMs:receipt.elapsedMs,busyMs,heights}));
