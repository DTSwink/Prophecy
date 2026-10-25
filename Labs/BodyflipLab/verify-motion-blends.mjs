import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),R=require('./recovery.js');
const checks=[],check=(label,ok)=>{assert(ok,label);checks.push(label);};
const distance=(a,b)=>R.length(R.sub(a,b)),h=1e-6;
const local=(p,parents)=>R.localize(p.points,p.q,parents);
const rates=(a,b,dt)=>a.q.map((q,i)=>R.mul(R.qlog(R.qm(b.q[i],R.qinv(q))),1/dt));
function boundary(sample,time,parents,bones,reference=null){
 const before=local(sample(time-h),parents),at=local(sample(time),parents),after=local(sample(time+h),parents);
 const left=rates(before,at,h),right=rates(at,after,h);
 let expected=left.map(()=>[0,0,0]);
 if(reference){const a=local(reference(time-h),parents),b=local(reference(time),parents),c=local(reference(time+h),parents),v0=rates(a,b,h),v1=rates(b,c,h);expected=v0.map((v,i)=>R.sub(v1[i],v));}
 return Math.max(...bones.map(i=>distance(R.sub(right[i],left[i]),expected[i])));
}
const parents=[-1,0],source=t=>R.fk({p:[[t,0,0],[0,1,0]],q:[R.qexp([0,t*.4,0]),R.qm(R.qexp([t*3,0,t]),R.qexp([0,.7,0]))]},parents);
const target=t=>R.fk({p:[[2+t*.2,0,0],[0,1,0]],q:[R.qexp([0,.8-t*.3,0]),R.qexp([.8,t*2,0])]},parents);
const transition=C.transition(source,target,.2,parents),sample=t=>t<0?source(t):transition(t);
check('Incoming angular velocity survives a non-collinear rotation transition',boundary(sample,0,parents,[0,1])<.003);
check('Target angular velocity is reached without stopping',boundary(sample,.2,parents,[0,1])<.003);
check('Incoming root velocity survives',distance(R.mul(R.sub(transition(h).points[0],transition(0).points[0]),1/h),[1,0,0])<.001);
check('Fixed bone lengths survive the blend',Array.from({length:41},(_,i)=>sample(i*.005)).every(p=>Math.abs(distance(p.points[1],p.points[0])-1)<1e-9));
check('Zero duration means immediate target',JSON.stringify(C.transition(source,target,0,parents)(.1))===JSON.stringify(target(.1)));
const repeat=JSON.stringify(transition(.08));transition(.18);transition(0);check('Sampling order does not affect transitions',JSON.stringify(transition(.08))===repeat);
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),m=read('data/manifest.json'),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const response=await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:0,drawn:true})});assert(response.ok);const run=F.decodeNN(await response.json());
const settings=C.sanitize({ramps:false,platforms:[{id:'floor',position:[0,-.2,0],size:[3.6,.4,66],rotation:[0,0,0,1]}]}),flight=F.sequence(run,jumps,settings,m.parents),a=flight.segments[0];
const support=[a.support.leg.hip,a.support.leg.knee,a.support.leg.foot,a.support.leg.toe],body=m.parents.map((_,i)=>i).filter(i=>i>1&&!support.includes(i));
const motion=t=>a.sample(t).pose,errors={};
const clip=F.trimStart(jumps.find(j=>j.name===a.start)),original=t=>F.at(clip,a.animationTime(t-a.jumpStart),m.parents);
for(const [name,time,bones] of [['push',a.jumpStart,body],['bodyEnd',a.jumpStart+settings.jumpBlend,body],['release',a.airStart,support],['legEnd',a.airStart+settings.legBlend,support],['fallLoop',a.jumpStart+a.loopStart,body],['fallLoopEnd',a.jumpStart+a.loopStart+.25,body]]){
 errors[name]=boundary(motion,time,m.parents,bones,name==='bodyEnd'?original:null);check('Moving joint continuity at '+name+' '+errors[name],errors[name]<.05);
}
const ankle=m.names.indexOf('foot_l'),pelvis=m.names.indexOf('pelvis'),relative=t=>{const p=motion(t);return R.sub(p.points[ankle],p.points[pelvis]);};
const advance=(relative(1)[2]-relative(59/60)[2])*100;
check('Reported left leg keeps advancing through frames 59-60',advance>2);
const failSettings=C.sanitize({...settings,jumpFoot:'L',supportSpeed:1,supportTrigger:0}),failed=F.sequence(run,jumps,failSettings,m.parents).segments[0];
check('Failure fixture actually aborts',Number.isFinite(failed.abortTime));
errors.abort=boundary(t=>failed.sample(t).pose,failed.abortTime,m.parents,[failed.support.leg.hip,failed.support.leg.knee,failed.support.leg.foot,failed.support.leg.toe]);
check('Abort retains outgoing leg velocity',errors.abort<.05);
// A short ledge exercises the carrier's fall transition using its actual gait.
const edge=F.sequence(run,jumps,{...settings,jumpEvents:[],platforms:[{id:'floor',position:[0,-.2,0],size:[3.6,.4,4],rotation:[0,0,0,1]}]},m.parents);
let falling=null;for(let i=1;i<180;i++){if(edge.sample(i/240).phase==='FALL'){falling=i/240;break;}}
check('Ledge fixture enters fall',falling!==null);
const previous=edge.sample(falling-1/240).pose,current=edge.sample(falling).pose,next=edge.sample(falling+1/240).pose;
const fallStep=distance(R.sub(next.points[ankle],next.points[pelvis]),R.sub(current.points[ankle],current.points[pelvis]));
const priorStep=distance(R.sub(current.points[ankle],current.points[pelvis]),R.sub(previous.points[ankle],previous.points[pelvis]));
check('Ledge entry does not stop the free leg',fallStep>priorStep*.5);
// Attack clip lead and return use the same transition machinery; the authored
// clip and hit-window timing stay intact.
const attack={duration:1,meta:{fps:60},poses:Array.from({length:61},(_,i)=>source(i/60))},idle=target(0);
const attackSample=t=>C.sample(attack,t,idle,parents);
for(const time of [0,.15,1.15,1.6])check('Attack blend velocity continuity at '+time,boundary(attackSample,time,parents,[0,1])<.02);
let maxAttackError=0;
for(const family of m.clips){
 const meta=family.variants[0],bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),clip=C.decode(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),m.names,m.parents),rest=C.poseFromShared(m),sample=t=>C.sample(clip,t,rest,m.parents),bones=m.parents.map((_,i)=>i);
 for(const time of [0,.15,.15+clip.duration,.6+clip.duration])maxAttackError=Math.max(maxAttackError,boundary(sample,time,m.parents,bones));
 check('Authored attack entry/return stays finite '+family.name,[0,.075,.15,.15+clip.duration,.4+clip.duration,.6+clip.duration].every(t=>sample(t).points.every(p=>p.every(Number.isFinite))));
}
check('Authored melee and sword attacks preserve boundary velocities',maxAttackError<.05);
console.log(JSON.stringify({passed:checks.length,frame59to60AdvanceCm:advance,angularVelocityErrors:errors,fallStep,priorStep,maxAttackError}));
