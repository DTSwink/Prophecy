import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js'),F=require('./flight.js'),M=require('./jump-motion.js'),G=require('./space-gym.js'),I=require('./idle.js'),Mass=require('./mass.js'),Target=require('./target-rig.js'),Recoil=require('./spin-response.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),buffer=n=>{const b=fs.readFileSync(new URL(n,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),idle=I.create(read('data/idle.json'),buffer('data/idle.bin'),manifest).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),rig=Mass.model(names,parents,reference),target=Target.create(names,parents,reference),rad=Math.PI/180;
const rotationError=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),localError=(a,b)=>Math.max(...a.q.slice(2).map((q,i)=>rotationError(q,b.q[i+2]))),source=t=>({pose:idle.sample(t),root:idle.sample(t).points[0],phase:'SPACE'}),reports=[];

// Distinct joint distances must produce distinct progress, not just a shared
// clock curve. Check entry and clearing against their actual local rotations.
const easeChecks=[];
for(const clearing of [false,true])for(const exponent of [1,2,3]){
 const clip=M.poses[0],local=R.localize(source(0).pose.points,source(0).pose.q,parents);
 for(let i=2;i<names.length;i++)local.q[i]=clip.locals[0].q[i];
 const target=structuredClone(local.q),indices=['upperarm_l','upperarm_r'].map(n=>names.indexOf(n)),angles=[45,135].map(d=>d*rad);
 indices.forEach((j,i)=>local.q[j]=R.qm(R.qexp([angles[i],0,0]),target[j]));const from=R.fk(local,parents);
 const options=C.sanitize({poseBlendIn:.4,poseBlendDistance:0,poseEaseIn:.15,poseEaseOut:.5,poseExponent:exponent,poseTuning:{pose1:{wobbleAmplitude:0}}});
 const segment={airStart:0,jumpStart:0,abortTime:Infinity,sample:()=>({pose:from,airPoseBase:target,jumpMotion:{pose:'pose1'}})},event={pose:clearing?'none':'pose1',poseOut:.4};
 const track=M.create(event,segment,jumps,names,parents,options),remaining=t=>{const f=track.sample(t),q=R.localize(f.pose.points,f.pose.q,parents).q;return indices.map(j=>rotationError(q[j],target[j]));};
 const early=remaining(.02),progress=early.map((r,i)=>1-r/angles[i]);
 if(exponent===1)assert(Math.abs(progress[0]-progress[1])<1e-10,'exponent 1 uses common progress');
 else assert(progress[1]>progress[0],'farther joint catches up faster proportionally');
 let previous=angles;for(let i=1;i<=80;i++){const r=remaining(i*.005);assert(r.every((v,j)=>v<=previous[j]+1e-10),'no overshoot/reversal');previous=r;}
 assert(Math.max(...remaining(.4))<1e-10,'exact finish at existing duration');assert(Math.max(...remaining(.4-1e-5))<1e-7,'smooth finish without terminal snap');
 assert.deepEqual(remaining(.02),early,'reverse seek deterministic');
 easeChecks.push({clearing,exponent,nearProgress:progress[0],farProgress:progress[1]});
}
const slowStart=M.transitionProgress(.1,{poseEaseIn:1,poseEaseOut:.5}),fastStart=M.transitionProgress(.1,{poseEaseIn:0,poseEaseOut:.5});assert(slowStart<fastStart,'ease in softens start independently');
const tail=out=>1-M.transitionProgress(.999,{poseEaseIn:0,poseEaseOut:out});assert(tail(1)<tail(.5)&&tail(.5)<tail(0),'ease out reduces end speed independently');

const timingChecks=[];
for(const weight of [0,.5,1])for(const degrees of [0,45,90,180]){
 const clip=M.poses[0],local=R.localize(source(0).pose.points,source(0).pose.q,parents);for(let i=2;i<names.length;i++)local.q[i]=clip.locals[0].q[i];
 const destination=local.q.slice();local.q[names.indexOf('upperarm_l')]=R.qm(R.qexp([degrees*rad,0,0]),local.q[names.indexOf('upperarm_l')]);const from=R.fk(local,parents),options=C.sanitize({poseBlendDistance:weight,poseTuning:{pose1:{wobbleAmplitude:0}}}),event={pose:'pose1',poseIn:.2,poseOut:.3},segment={airStart:0,jumpStart:0,abortTime:Infinity,sample:()=>({pose:from,airPoseBase:destination,jumpMotion:{pose:'pose1'}})};
 for(const clear of [false,true]){const track=M.create({...event,pose:clear?'none':'pose1'},segment,jumps,names,parents,options),seconds=clear?.3:.2,expected=Math.max(1/60,seconds*(1-weight+weight*degrees/90));assert(Math.abs(track.duration-expected)<1e-10,'frozen distance rule '+degrees+' / '+weight);const duration=track.duration;track.sample(3);track.sample(.1);assert.equal(track.duration,duration,'duration does not chase current distance');timingChecks.push({degrees,weight,clear,duration});}
 const turn=R.qexp([1.2,-.4,.8]),rotated={...segment,sample:()=>({pose:Mass.rotateAboutCOM(from,turn,rig)})},track=M.create(event,rotated,jumps,names,parents,options);assert(Math.abs(track.duration-M.create(event,segment,jumps,names,parents,options).duration)<1e-10,'flipping does not change measured articulation distance');
}

for(const clip of M.poses){
 const settings=C.sanitize({mode:'spaceGym',spinLag:0,momentum3D:false,poseBlendDistance:0,poseResponseSpeed:360,poseTuning:{[clip.id]:{wobbleAmplitude:0}}}),event={id:'pose',time:0,jumpPercent:0,spinVersion:2,pose:clip.id,poseIn:.2,poseHold:2,poseOut:.3},segment={sample:source,airStart:0,jumpStart:0,abortTime:Infinity},track=M.create(event,segment,jumps,names,parents,settings),frame=track.sample(.5),neutral=R.localize(frame.pose.points,frame.pose.q,parents);
 assert(localError(neutral,clip.locals[clip.neutralFrame])<1e-10,'neutral authored frame '+clip.name);

 let maxExactError=0;
 const assertCarrier=(a,b)=>{for(const i of [0,1]){assert(rotationError(a.q[i],b.q[i])<1e-10,'pose leaves root/pelvis rotation unchanged');assert(R.length(R.sub(a.points[i],b.points[i]))<1e-10,'pose leaves root/pelvis position unchanged');}};
 for(const t of [.05,.2,.5,3,100]){const out=track.sample(t);const expected=structuredClone(source(t).pose);expected.q[1]=R.qslerp(expected.q[1],source(0).pose.q[1],out.jumpMotion?.poseWeight||0);assertCarrier(out.pose,expected);if(t>=.2){assert.equal(out.jumpMotion.poseWeight,1,'no automatic pose expiry');assert(localError(R.localize(out.pose.points,out.pose.q,parents),clip.locals[0])<1e-10);}}
 for(const turn of [R.qexp([Math.PI/2,0,0]),R.qexp([Math.PI,0,0]),R.qexp([0,0,Math.PI]),R.qexp([.7,-.4,.2])]){
  const rotated={...segment,sample:t=>({...source(t),pose:Mass.rotateAboutCOM(source(t).pose,turn,rig)})},tilted=M.create(event,rotated,jumps,names,parents,settings).sample(.5);const expected=structuredClone(rotated.sample(.5).pose);expected.q[1]=rotated.sample(0).pose.q[1];assertCarrier(tilted.pose,expected);assert(localError(R.localize(tilted.pose.points,tilted.pose.q,parents),neutral)<1e-10,'same pose relative to pelvis throughout flips');
  for(const sign of [-1,1]){const omega=R.mul(R.rotate(tilted.pose.q[1],[1,0,0]),sign*360*rad),out=tilted.poseMotion.apply(tilted.pose,omega,tilted.poseMotion.mask);assertCarrier(out.pose,tilted.pose);}
 }

 for(const sign of [-1,1])for(const fraction of [.5,1,2]){
  const up=R.rotate(frame.pose.q[1],[1,0,0]),omega=R.mul(up,sign*360*rad*fraction),out=frame.poseMotion.apply(frame.pose,omega,frame.poseMotion.mask),local=R.localize(out.pose.points,out.pose.q,parents),expected=clip.locals[sign>0?clip.positiveFrame:clip.negativeFrame].q.map((q,i)=>R.qslerp(clip.locals[0].q[i],q,Math.min(1,fraction)));maxExactError=Math.max(maxExactError,localError(local,{q:expected}));
  assertCarrier(out.pose,frame.pose);
  const turn=R.qexp([.7,-.4,.2]),posed=Mass.rotateAboutCOM(frame.pose,turn,rig),reframed=frame.poseMotion.apply(posed,R.rotate(turn,omega),frame.poseMotion.mask);assert(localError(reframed.pose,Mass.rotateAboutCOM(out.pose,turn,rig))<1e-10,'world orientation invariant');
 }
 assert(maxExactError<1e-10,'full and partial authored extremes');
 const inverted=M.create(event,segment,jumps,names,parents,{...settings,invertPoseVariants:true}).sample(.5);assert(localError(inverted.pose,frame.pose)<1e-10,'inversion leaves neutral pose unchanged');
 for(const sign of [-1,1])for(const fraction of [.5,1]){const omega=R.mul(R.rotate(frame.pose.q[1],[1,0,0]),sign*360*rad*fraction),flipped=inverted.poseMotion.apply(inverted.pose,omega,inverted.poseMotion.mask),opposite=frame.poseMotion.apply(frame.pose,R.mul(omega,-1),frame.poseMotion.mask);assert(localError(flipped.pose,opposite.pose)<1e-10,'inversion swaps only the variant frames');assert(Math.sign(flipped.poseSpeed)===sign,'inversion does not reverse measured spin');assertCarrier(flipped.pose,inverted.pose);}

 const tinyRecoil=Recoil.create(names,parents,reference,.6).apply(frame.pose,{x:Array(16).fill(1e-8),v:Array(16).fill(0)});assert(localError(R.localize(tinyRecoil.points,tinyRecoil.q,parents),neutral)<1e-6,'tiny spin recoil cannot clamp the authored pose');
 const up=R.rotate(frame.pose.q[1],[1,0,0]),perp=R.mul(R.unit(R.cross(up,Math.abs(up[1])<.8?[0,1,0]:[1,0,0])),100),unchanged=frame.poseMotion.apply(frame.pose,perp,frame.poseMotion.mask);assert(Math.abs(unchanged.poseSpeed)<1e-10,'only pelvis-up projection contributes');
 const tuning={...settings.poseTuning,[clip.id]:{wobbleSpeed:1,wobbleAmplitude:.1}},w=M.create(event,segment,jumps,names,parents,{...settings,poseTuning:tuning}),wave=R.localize(w.sample(.5).pose.points,w.sample(.5).pose.q,parents);assert(rotationError(wave.q[1],neutral.q[1])<1e-10,'wobble leaves pelvis unchanged');assert(localError(wave,neutral)>.001,'falling wobble adds motion');
 const double=M.create(event,segment,jumps,names,parents,{...settings,poseTuning:{...tuning,[clip.id]:{...tuning[clip.id],wobbleSpeed:2}}});assert(localError(wave,R.localize(double.sample(.25).pose.points,double.sample(.25).pose.q,parents))<1e-10,'wobble speed scales time');
 let limit=0;for(const d of target.joints.inspect(frame.pose))limit=Math.max(limit,d.angularError);
 const runs=[];
 for(const sign of [-1,1]){
  const e={...event,instantSpin:true,flip:0,twist:sign*200,turnAxis:3},gym=G.sequence(idle,jumps,settings,parents,[e],null,reference);let last=null,maxStep=0,maxSpeed=0,maxSpeedStep=0,previousSpeed=0;
  for(let i=0;i<=660;i++){const f=gym.sample(i/240);assert(f.pose.points.flat().concat(f.pose.q.flat()).every(Number.isFinite));if(last)maxStep=Math.max(maxStep,...f.pose.q.map((q,j)=>rotationError(q,last.pose.q[j])));const speed=f.jumpMotion?.poseSpeed||0;maxSpeed=Math.max(maxSpeed,Math.abs(speed));maxSpeedStep=Math.max(maxSpeedStep,Math.abs(speed-previousSpeed));previousSpeed=speed;last=f;}
  const out=gym.sample(1);assert(Math.sign(out.jumpMotion.poseSpeed)===sign,'live projected velocity sign '+clip.name);assert.equal(out.jumpMotion.poseVariant,sign>0?clip.positiveFrame:clip.negativeFrame);assert(maxStep<.2,'bounded consecutive-frame rotation '+clip.name);const saved=JSON.stringify(gym.sample(1));gym.sample(.1);assert.equal(JSON.stringify(gym.sample(1)),saved,'seek determinism');runs.push({sign,maxStep,maxSpeed,maxSpeedStep,speed:out.jumpMotion.poseSpeed});
 }
 reports.push({name:clip.name,maxExactError,sourceLimitError:limit,runs});
}


// A pose holds without a timer, changes on the next authored pose, and an
// explicit No pose marker restores the moving base in the current pelvis frame.
const chainSettings=C.sanitize({mode:'spaceGym',momentum3D:false,spinLag:0,spaceFallAnimation:true,poseTuning:Object.fromEntries(M.poses.map(p=>[p.id,{wobbleAmplitude:0}]))}),first={id:'pose',time:0,jumpPercent:0,spinVersion:2,flip:120,twist:200,pose:'pose4',poseIn:.2},next={...first,id:'next',time:1.1,pose:'pose2'},clear={id:'clear',time:2.5,jumpPercent:0,spinVersion:2,pose:'none',poseOut:.3},chain=G.sequence(idle,jumps,chainSettings,parents,[first,next,clear],null,reference),unposed=G.sequence(idle,jumps,chainSettings,parents,[],null,reference);
for(const [t,id] of [[1,'pose4'],[2.4,'pose2']])assert.equal(chain.sample(t).jumpMotion.pose,id,'pose persists until another marker');
const cleared=chain.sample(3.1);assert.equal(cleared.jumpMotion.poseWeight,0);assert.equal(cleared.airPoseBase,null);const chainError=localError(R.localize(cleared.pose.points,cleared.pose.q,parents),(()=>{const p=target.project(unposed.sample(3.1).pose);return R.localize(p.points,p.q,parents);})());assert(chainError<1e-8,'No pose restores ongoing base articulation');
let markerStep=0;for(const t of [1.1,1.3,2.5,2.8]){const a=chain.sample(t-1e-7),b=chain.sample(t+1e-7);markerStep=Math.max(markerStep,...a.pose.q.map((q,i)=>rotationError(q,b.pose.q[i])));}assert(markerStep<1e-3,'continuous change and clear while flipping');
const remembered=JSON.stringify(chain.sample(2));chain.sample(.1);assert.equal(JSON.stringify(chain.sample(2)),remembered,'persistent pose reverse seek');

const extremes=[];
for(const [pose,responseSpeed,responseTime,momentum3D] of [['pose1',1,.05,false],['pose2',3600,1,true],['pose3',1,.05,true],['pose4',3600,.05,false]]){
 const options=C.sanitize({mode:'spaceGym',momentum3D,spinLag:.6,poseResponseSpeed:responseSpeed,poseResponseTime:responseTime,poseTuning:{[pose]:{wobbleSpeed:4,wobbleAmplitude:1}}}),e={...first,pose,poseIn:.2,poseHold:1,poseOut:.3},sequence=G.sequence(idle,jumps,options,parents,[e],null,reference);let residual=0;
 for(let i=1;i<=360;i++){const frame=sequence.sample(i/240);assert(frame.pose.q.flat().every(Number.isFinite));residual=Math.max(residual,Math.abs(frame.jumpMotion?.poseResponseError||0));}assert(residual<1e-4,'response converges at slider extremes '+pose);extremes.push({pose,responseSpeed,responseTime,momentum3D,residual});
}

const jumpSettings=C.sanitize({mode:'idle',ramps:false,momentum3D:false,spinLag:0,platforms:[{id:'floor',position:[0,-.2,0],size:[40,.4,60],rotation:[0,0,0,1]}],jumpEvents:[{id:'jump',time:.1,spinVersion:2,twist:180,pose:'pose4',poseIn:.2,poseHold:.5,poseOut:.25}]}),jump=F.sequence(idle,jumps,jumpSettings,parents,reference,null,null,{horizon:1.2}),jumpSegment=jump.segments[0],airborne=jump.sample(jumpSegment.airStart+.3);
assert(airborne.pose.points.flat().concat(airborne.pose.q.flat()).every(Number.isFinite));assert.equal(airborne.jumpMotion.pose,'pose4');assert(Number.isFinite(airborne.jumpMotion.poseSpeed)&&Math.abs(airborne.jumpMotion.poseSpeed)>1e-3&&airborne.jumpMotion.poseResponseError!==undefined,'grounded jump uses measured airborne pose response');
console.log(JSON.stringify({passed:true,timingChecks:timingChecks.length,chainError,markerStep,reports,extremes,jump:{airStart:jumpSegment.airStart,speed:airborne.jumpMotion.poseSpeed}},null,2));
