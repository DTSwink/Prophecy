import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),K=require('./airborne-motion.js'),H=require('./attack-inertia.js'),L=require('./leg-response.js'),A=require('./jump-attack.js'),F=require('./flight.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),metadata=read('data/vanilla.json'),hinges=H.legHinges(names,reference);
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),distance=(a,b)=>R.length(R.sub(a,b));
const poseError=(a,b)=>Math.max(...a.q.map((q,i)=>angle(q,b.q[i])),...a.points.map((p,i)=>distance(p,b.points[i])));
const run=F.decodeNN(read('data/run-default-drawn.json'));
const base=t=>{const f=Math.max(0,Math.min(run.poses.length-1,t*run.fps)),i=Math.min(run.poses.length-2,Math.floor(f));return C.blend(run.poses[i],run.poses[i+1],f-i,parents);};
let samples=0,maxEndpointError=0,maxStrikeDifference=0,maxCOMError=0,maxVelocityJump=0,maxReturnBacktrack=0,maxHitPoseError=0,maxFollowthroughError=0,minKnee=Infinity,maxKnee=0;
const results=[];let worstJoin=null,checking="";
function inspect(pose){
 assert(pose.points.flat().every(Number.isFinite));
 for(const h of hinges){const a=R.unit(R.sub(pose.points[h.knee],pose.points[h.hip])),b=R.unit(R.sub(pose.points[h.foot],pose.points[h.knee])),bend=Math.atan2(R.dot(R.cross(a,b),R.rotate(pose.q[h.knee],h.kneeAxis)),R.dot(a,b));minKnee=Math.min(minKnee,bend);maxKnee=Math.max(maxKnee,bend);}
 const local=R.localize(pose.points,pose.q,parents),rest=R.localize(reference.points,reference.q,parents);
 for(let i=2;i<names.length;i++)assert(Math.abs(R.length(local.p[i])-R.length(rest.p[i]))<.005,'Rigid sockets retained');
 samples++;
}
function joins(sample,times,baseline){
 const h=1e-6;
 // Remove the continuing NN/source curve: its existing frame-key velocity
 // changes must not be confused with a discontinuity added by recovery.
 for(const t of times){const poses=[t-h,t,t+h].map(s=>{const p=sample(s),b=baseline(s);return {q:p.q.map((q,i)=>R.qm(q,R.qinv(b.q[i])))};});for(let i=1;i<names.length;i++){const a=R.mul(R.qlog(R.qm(poses[1].q[i],R.qinv(poses[0].q[i]))),1/h),b=R.mul(R.qlog(R.qm(poses[2].q[i],R.qinv(poses[1].q[i]))),1/h);if(distance(a,b)>maxVelocityJump){maxVelocityJump=distance(a,b);worstJoin={checking,t,bone:names[i],jump:maxVelocityJump};}}}
}
for(const name of ['KickL','KickR']){checking=name;
 const meta=metadata.clips.find(c=>c.name===name),clip=C.decode(meta,bytes(meta.file),names,parents),motion=K.recording({clip,names,parents,reference});
 let strikeRoot=names.indexOf(C.effector(name));while(parents[strikeRoot]!==names.indexOf('pelvis'))strikeRoot=parents[strikeRoot];
 const options={source:motion.sample,names,parents,reference,duration:motion.stop+1.2,strikeRoot,strikeWeight:motion.strikeWeight,recoveryStart:motion.end,recoveryEnd:motion.stop},old=K.createBalanced(options),hitTime=motion.lead+meta.phases.hit/meta.fps,plan=K.returnFromHit(old,{start:hitTime,end:motion.stop,parents,pelvis:names.indexOf('pelvis')});
 assert.equal(plan.recoveryEnd,motion.stop,'Kick recovery ends on the original source end time');assert.equal(plan.duration,old.duration,'Do not extend the existing preview timeline');
 for(let t=0;t<=hitTime;t+=1/120)maxStrikeDifference=Math.max(maxStrikeDifference,poseError(old.sample(t),plan.sample(t)));
 maxHitPoseError=Math.max(maxHitPoseError,poseError(plan.sample(hitTime),old.sample(hitTime)),poseError(plan.sample(hitTime+1e-7),old.sample(hitTime)));
 const rest=R.localize(plan.sample(0).points,plan.sample(0).q,parents);let previousErrors=null;
 for(let t=hitTime;t<=plan.duration;t+=1/120){const pose=plan.sample(t),local=R.localize(pose.points,pose.q,parents),errors=[angle(local.q[names.indexOf('pelvis')],rest.q[names.indexOf('pelvis')])];for(let i=0;i<names.length;i++)if(i!==names.indexOf('pelvis'))maxFollowthroughError=Math.max(maxFollowthroughError,angle(pose.q[i],old.sample(t).q[i]));if(previousErrors)maxReturnBacktrack=Math.max(maxReturnBacktrack,...errors.map((v,i)=>v-previousErrors[i]));previousErrors=errors;inspect(pose);maxCOMError=Math.max(maxCOMError,distance(K.center(H.bodies(pose,plan.rig),plan.rig),plan.center));}
 const final=plan.sample(plan.recoveryEnd),endpoint=poseError(final,plan.sample(0));maxEndpointError=Math.max(maxEndpointError,endpoint);
 for(const t of [plan.recoveryEnd,plan.duration,100])maxEndpointError=Math.max(maxEndpointError,poseError(plan.sample(t),plan.sample(0)));
 // Hit is now the requested turnaround, not a continuation of the outward
 // strike velocity. Pose must remain continuous; the final settle is C2.
 joins(t=>plan.sample(t),[plan.recoveryEnd],t=>plan.uncorrected(t));
 const saved=JSON.stringify(plan.sample(1.3));plan.sample(0);plan.sample(20);assert.equal(JSON.stringify(plan.sample(1.3)),saved);
 results.push({name,path:'full-body kick / pelvis return',returnStart:plan.recoveryStart,returnEnd:plan.recoveryEnd,endpointError:endpoint});
}
// All sixteen scheduled attack animations use the same return. A moving NN
// baseline proves recovery follows the gait instead of freezing the start pose.
for(const meta of metadata.clips){checking=meta.name;
 const clip=C.decode(meta,bytes(meta.file),names,parents),catalog=new Map([[meta.name,clip]]),segment={sample:t=>({pose:base(t)}),airStart:.35,jumpStart:.35,abortTime:Infinity};
 const action=A.create({attack:meta.name},segment,catalog,names,parents,{...C.defaults,pelvisAttackCompensation:1,softAttackLegs:true},reference),plan=action.inertia;
 const start=action.hitTime,end=action.returnEnd;
 assert.equal(action.recovery.start,start,'Every attack returns from Hit');assert.equal(end,action.end+C.sanitizeJump({attack:meta.name}).attackOut,'Finish inside the existing attackOut, without extra motion');
 const old=L.create({source:t=>plan.samplePlanned(t),base,start:action.start,stop:plan.stop,names,parents,reference,hinges,anticipation:.06,sampleRate:60});
 for(let t=action.start;t<=start;t+=1/30)maxStrikeDifference=Math.max(maxStrikeDifference,poseError(old.sample(t),action.sample(t).pose));
 for(let t=start;t<=end+.1;t+=1/120)inspect(action.sample(t).pose);
 let endpoint=0;for(const t of [end,end+.5,end+2])endpoint=Math.max(endpoint,poseError(action.sample(t).pose,base(t)));
 maxEndpointError=Math.max(maxEndpointError,endpoint);joins(t=>action.sample(t).pose,[end],base);
 results.push({name:meta.name,path:'scheduled / moving gait',returnStart:start,returnEnd:end,endpointError:endpoint});
}
assert(maxStrikeDifference<1e-8,'Approved strike must be unchanged');
assert(maxEndpointError<1e-8,'Every joint and position must return exactly to the ongoing base pose');
assert(maxFollowthroughError<1e-8,'Preserve every non-pelvis source orientation throughout kick recovery');
assert(maxCOMError<1e-8,'Returning orientation must not move the kick COM');
assert(maxReturnBacktrack<1e-8&&maxHitPoseError<1e-5,'No post-Hit pelvis reversal or pose discontinuity: '+JSON.stringify({maxReturnBacktrack,maxHitPoseError}));
assert(minKnee>=-1e-5&&maxKnee<=150*Math.PI/180+1e-5,'No knee inversion or overfold during recovery');
assert(maxVelocityJump<.05,'No angular-velocity snap entering or leaving recovery: '+JSON.stringify(worstJoin));
const result={samples,maxStrikeDifference,maxHitPoseError,maxFollowthroughError,maxReturnBacktrack,maxEndpointError,maxCOMError,maxVelocityJump,kneeRangeDegrees:[minKnee,maxKnee].map(v=>v*180/Math.PI),recovery:'Pelvis-only Hit return; all other source motion continues; original end times unchanged.',results};
fs.writeFileSync(new URL('attack-return-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
