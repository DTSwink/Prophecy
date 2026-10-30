import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),M=require('./jump-motion.js'),R=require('./recovery.js'),I=require('./idle.js'),G=require('./space-gym.js'),Scenes=require('./scenes.js'),Target=require('./target-rig.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),bytes=fs.readFileSync(new URL('data/idle.bin',import.meta.url)),idle=I.create(read('data/idle.json'),bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),m).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),rig=Target.create(names,parents,reference);
const checks=[],check=(name,ok)=>{assert(ok,name);checks.push(name);},distance=(a,b)=>R.length(R.sub(a,b)),error=(a,b)=>Math.max(...a.points.map((p,i)=>distance(p,b.points[i])));
const event={id:'first',time:.1,...C.sanitizeJump({spinVersion:2,flip:180,twist:-90,turnDelay:.15,turnAxis:3})},settings=C.sanitize({mode:'idle',ramps:false,spinInertia:0,platforms:[{id:'floor',position:[0,-.2,0],size:[40,.4,60],rotation:[0,0,0,1]}],jumpEvents:[event]});
const base=F.sequence(idle,jumps,{...settings,jumpEvents:[{...event,flip:null,twist:null}]},parents,reference,null,null,{horizon:1.2}),seq=F.sequence(idle,jumps,settings,parents,reference,null,null,{horizon:1.2}),s=seq.segments[0],b=base.segments[0];
check('Rate commands do not allocate a pose override',s.motion===null&&b.motion===null);
check('New spin begins after the real push, preserving its timing',s.jumpStart===b.jumpStart&&s.airStart===b.airStart);
let pinError=0;for(let t=0;t<s.airStart;t+=1/120)pinError=Math.max(pinError,error(s.sample(t).pose,b.sample(t).pose));check('New command leaves preceding support poses unchanged',pinError<1e-8);
check('Delay holds the previous rate',s.spin.sample(s.airStart+.14).spin.target.flip===0);
check('Rate persists beyond the obsolete duration',Math.abs(s.spin.sample(s.airStart+2).spin.target.flip-180)<1e-9);
const saved=JSON.stringify(seq.sample(.7));seq.sample(2);seq.sample(0);check('Reverse seeks preserve the same choreography',JSON.stringify(seq.sample(.7))===saved);
const corrupt=C.sanitizeJump({spinVersion:2,flip:NaN,twist:Infinity,turnDuration:0,turnDelay:-1,turnAxis:90,pose:'unknown',poseIn:0,poseOut:-3});check('Invalid optional rates inherit, timings remain finite',corrupt.flip===null&&corrupt.twist===null&&corrupt.turnDelay===0&&corrupt.turnAxis===null&&corrupt.pose==='none'&&corrupt.poseIn>0&&corrupt.poseOut>0);
check('No-pose is a true bypass',M.poseWeight(.3,{...C.jumpDefaults,pose:'none'})===0);
const phases=C.sanitizeJump({pose:'pose1',poseIn:.2,poseHold:.3,poseOut:.25});check('Pose eases in, holds, and eases out',M.poseWeight(0,phases)===0&&Math.abs(M.poseWeight(.1,phases)-.5)<1e-9&&M.poseWeight(.35,phases)===1&&Math.abs(M.poseWeight(.625,phases)-.5)<1e-9&&M.poseWeight(.75,phases)===0);
const measurements=[];
for(const pose of ['pose1','pose2','pose3','pose4']){
 const e={id:'pose',time:0,...C.sanitizeJump({...event,jumpPercent:0,pose,turnDelay:0})},gym=G.sequence(idle,jumps,{...settings,mode:'spaceGym'},parents,[e],null,reference);let maxLimit=0,maxAnchor=0,maxStep=0,previous=null;
 for(let i=0;i<=360;i++){const p=gym.sample(i/240).pose;assert(p.points.flat().concat(p.q.flat()).every(Number.isFinite));for(const d of rig.joints.inspect(p)){maxLimit=Math.max(maxLimit,d.angularError);maxAnchor=Math.max(maxAnchor,d.anchorError);}if(previous)maxStep=Math.max(maxStep,error(p,previous));previous=p;}
 check('Legal knees and other joints '+pose,maxLimit<1e-8);check('Fixed bone attachments '+pose,maxAnchor<1e-9);check('No pose-entry or pose-exit teleport '+pose,maxStep<.08);
 // Articulation returns to its moving source; accumulated orientation remains.
 const normal=G.sequence(idle,jumps,{...settings,mode:'spaceGym'},parents,[{...e,pose:'none'}],null,reference),a=R.localize(gym.sample(1.5).pose.points,gym.sample(1.5).pose.q,parents),b=R.localize(normal.sample(1.5).pose.points,normal.sample(1.5).pose.q,parents);
 check('Pose returns to moving animation without undoing spin '+pose,a.q.slice(2).every((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(b.q[i+2]))))<1e-6));measurements.push({pose,maxLimit,maxAnchor,maxStep});
}
const state={settings:{...settings,jumpEvents:[event]},playback:{time:2,playing:false}},library=Scenes.open(state),copied=Scenes.copy(library,'Other','other'),pack=Scenes.pack(Scenes.select(Scenes.open(JSON.parse(JSON.stringify(Scenes.pack(copied)))),'original'));
check('Rate commands survive scene copy/switch/save',JSON.stringify(pack.settings.jumpEvents)===JSON.stringify(state.settings.jumpEvents));
console.log(JSON.stringify({passed:true,checks:checks.length,pinError,measurements},null,2));
