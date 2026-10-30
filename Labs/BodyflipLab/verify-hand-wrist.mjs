// Historical contact/COM fixtures use equal tier times to retain their original loading.
// Bounded wrist/contact audit. Frozen local motions only; no NN or UI.
import fs from 'node:fs';import {createRequire} from 'node:module';import assert from 'node:assert/strict';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),H=require('./hand-support.js'),F=require('./flight.js'),W=require('./wrist.js'),I=require('./idle.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),buffer=n=>{const b=fs.readFileSync(new URL(n,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),idle=I.create(read('data/idle.json'),buffer('data/idle.bin'),manifest);
const {add,sub,mul,dot,length,qm,qinv,qlog}=R,dist=(a,b)=>length(sub(a,b)),angle=(a,b)=>length(qlog(qm(a,qinv(b)))),reports=[];
function bank(){
 const meta=read('data/walk-drawn-phases.json'),count=Math.ceil(5*meta.fps)+2,width=3+meta.names.length*12,bytes=Buffer.alloc(count*width*4),fd=fs.openSync(new URL('data/walk-drawn-phases.bin',import.meta.url),'r');try{fs.readSync(fd,bytes,0,bytes.length,0);}finally{fs.closeSync(fd);}
 const roots=[],poses=[];for(let f=0;f<count;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}return F.decodeNN({...meta,duration:5,roots,poses});
}
const exactSettings=C.sanitize({loadYMs:100,loadFullMs:100,mode:'walk',motion:'kinematic',runSeconds:1,runPhase:0,jumpEarly:.1,jumpBlend:.2,legBlend:.2,handBend:.35,loadMs:100,rebound:.5,supportCone:30,supportReach:.99,supportTrigger:.05,supportAlpha:1,supportSpeed:800,jumpSkew:.5,matchLeg:true,surfaceIK:true,trimLoop:true,trimOut:2.55,airFlip:false,flipAngle:0,twistAngle:0,ramps:false,attack:'slashLD',jumpEvents:[{id:'first',time:56/60,surface:'floor',pushWith:'foot',flip:180},{id:'hand',time:1.8,surface:'auto',pushWith:'handL'}],platforms:[{id:'floor',position:[0,-.2,-.5599910537770252],size:[3.6,.4,66.20677485127891],rotation:[0,0,0,1]}]});
function audit(label,segment,sample,start,end){
 const l=segment.support.leg,initial=W.decompose(W.clampConstraint(l.wristStart)),r={label,pushed:Number.isFinite(segment.jumpStart)&&(!segment.bounce||segment.bounce.didPush),reason:segment.failureReason||segment.bounce?.limitReason||null,contact:segment.contactTime,release:segment.airStart,limitViolation:0,twistDrift:0,deviationDrift:0,pinError:0,contactResidual:0,minPalmGap:Infinity,minForearmGap:Infinity,rootResidual:0,seamPosition:0,seamRotation:0,halfTickAngle:0,halfTickRelativeAngle:0,samples:0};
 let previous=null;
 const times=Array.from({length:Math.ceil((end-start)*120)+1},(_,i)=>start+i/120).flatMap(t=>[t,t+1/480]).filter(t=>t<=end);
 for(const t of times){const frame=sample(t),p=frame.pose;assert(p.points.flat().every(Number.isFinite)&&p.q.flat().every(Number.isFinite),label+' finite');r.samples++;
  const active=frame.phase==='SUPPORT'||frame.supportState==='PIN';if(!active)continue;
  const a=l.wrist.inspect(p.q[l.knee],p.q[l.foot]);r.limitViolation=Math.max(r.limitViolation,a.ellipse-1,Math.abs(a.angle)-W.limits.twistMax);r.twistDrift=Math.max(r.twistDrift,Math.abs(a.angle-initial.angle));r.deviationDrift=Math.max(r.deviationDrift,Math.abs(a.swing[2]-initial.swing[2]));
  const relative=l.wrist.toConstraint(p.q[l.knee],p.q[l.foot]);
  if(previous&&t-previous.t<1/240+1e-9){r.halfTickAngle=Math.max(r.halfTickAngle,angle(p.q[l.foot],previous.q));r.halfTickRelativeAngle=Math.max(r.halfTickRelativeAngle,angle(relative,previous.relative));}previous={t,q:p.q[l.foot],relative};
  const n=segment.surface.normal,origin=segment.surface.origin,gap=v=>dot(sub(v,origin),n);r.minForearmGap=Math.min(r.minForearmGap,gap(p.points[l.knee])-.048,gap(p.points[l.foot])-.048);
  if(frame.supportState==='PIN'){
   const contact=segment.contactMotion.sample(t-segment.contactTime,frame.root);r.pinError=Math.max(r.pinError,dist(p.points[l.foot],contact.foot));r.contactResidual=Math.max(r.contactResidual,contact.residual||0);r.minPalmGap=Math.min(r.minPalmGap,...H.corners(p,l.foot,l.side).map(v=>gap(add(p.points[l.foot],v))));
   if(segment.bounce)r.rootResidual=Math.max(r.rootResidual,dist(frame.root,segment.bounce.sample(t-segment.contactTime).p));
  }
 }
 for(const t of [segment.supportStart,segment.contactTime,segment.jumpStart,segment.airStart])if(Number.isFinite(t)&&t>=start&&t<=end){const a=sample(t-1e-7).pose,b=sample(t+1e-7).pose;for(let i=1;i<names.length;i++){const d=dist(a.points[i],b.points[i]);if(d>r.seamPosition){r.seamPosition=d;r.seamWorst={time:t,bone:names[i]};}r.seamRotation=Math.max(r.seamRotation,angle(a.q[i],b.q[i]));}}
 const at=(start+end)/2,expected=JSON.stringify(sample(at));sample(end);sample(start);r.deterministic=JSON.stringify(sample(at))===expected;
 r.approach=segment.support.frames.slice(0,4).map(f=>({t:f.t,palmDistance:f.distance,wristDistance:dist(f.foot,f.target)}));reports.push(r);console.log(JSON.stringify(r));return r;
}
const started=performance.now(),exact=F.sequence(bank(),jumps,exactSettings,parents,reference,null,null,{horizon:2.55});audit('Exact inverted L',exact.segments[1],t=>exact.sample(t),1.8,Math.min(2.3,exact.segments[1].airStart+.22));
const snapshotTimes=Array.from({length:37},(_,i)=>1.75+i/60);snapshotTimes.push(1.816667);snapshotTimes.sort((a,b)=>a-b);fs.writeFileSync(new URL('../../Saved/BodyflipLab/HandReview/wrist-poses.json',import.meta.url),JSON.stringify({names,parents,reference,frames:snapshotTimes.map(time=>({time,...exact.sample(time)})),timing:{contact:exact.segments[1].contactTime,jump:exact.segments[1].jumpStart,release:exact.segments[1].airStart}}));
const floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,20],.4),base=C.sanitize({loadYMs:100,loadFullMs:100,mode:'idle',motion:'kinematic',ramps:false,surfaceIK:false,supportAlpha:0});
for(const gait of ['idle','walk','run'])for(const side of ['L','R']){
 const run=gait==='idle'?idle.motion():F.decodeNN(read('data/'+gait+'-default.json')),time=gait==='run'?.4:.1,settings={...base,mode:gait==='run'?'jump':gait,platforms:[S.platformRecord(floor)],jumpEvents:[{id:'h',time,pushWith:'hand'+side}]},seq=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:1.1}),seg=seq.segments[0];
 audit(gait+' floor '+side,seg,t=>seq.sample(t),time,Math.min(1.1,Number.isFinite(seg.airStart)?seg.airStart+.15:seg.abortTime+.03));
}
const edge=S.rectangle('edge',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,2.3],.4),edgeSequence=F.sequence(F.decodeNN(read('data/run-default.json')),jumps,{...base,mode:'jump',platforms:[S.platformRecord(edge)],jumpEvents:[{id:'edge',time:.4,pushWith:'handR'}]},parents,reference,null,null,{horizon:.8});
audit('Run past finite edge',edgeSequence.segments[0],t=>edgeSequence.sample(t),.4,edgeSequence.segments[0].abortTime+.03);
for(const [label,n,z] of [['slope',[0,Math.SQRT1_2,-Math.SQRT1_2],.35],['wall',[0,0,-1],.55]])for(const side of ['L','R']){
 // Both surfaces are in front of the rig; unlike a plane placed next to a
 // wrist, they do not cut through the source character's torso or legs.
 const p=idle.sample(0),u=[1,0,0],v=R.cross(u,n),surface=S.rectangle(label,[0,0,z],u,v,[-2,2,-2,2]),seg=F.create(idle.motion(),jumps,base,parents,reference,{hand:'hand'+side,time:0,surface,poseAt:()=>p,continueAt:()=>({pose:p,root:p.points[0],phase:'IDLE',speed:0,vy:0,airTime:0}),velocityAt:()=>[0,0,0]});
 audit('Isolated '+label+' '+side,seg,t=>seg.sample(t),0,Math.min(.8,Number.isFinite(seg.airStart)?seg.airStart+.12:seg.abortTime+.03));
}
console.log(JSON.stringify({elapsedMs:performance.now()-started,cases:reports.length}));
if(process.env.WRIST_AUDIT_ONLY!=='1')for(const r of reports){
 assert(r.limitViolation<1e-7,r.label+' respects wrist limits');assert(r.deterministic,r.label+' deterministic');assert(r.pinError<3e-5,r.label+' preserves pin');assert(r.contactResidual<3e-5,r.label+' contact solve converges');assert(r.twistDrift<1e-5,r.label+' adds no axial twist');assert(r.deviationDrift<1e-5,r.label+' adds no sideways bend');
 assert(r.minPalmGap>=-1e-6,r.label+' palm stays outside contacted plane');assert(r.minForearmGap>=-1e-6,r.label+' forearm stays outside contacted plane');
 assert(r.seamPosition<.001,r.label+' position continuous at contact/release');assert(r.seamRotation<.003,r.label+' rotation continuous at contact/release');
 if(/^(idle|walk|run) floor/.test(r.label))assert(r.pushed,r.label+' rotating palm clearance does not falsely abort a reachable push');
 if(r.label==='Run past finite edge')assert(!r.pushed&&r.reason==='Distance growing','Finite edge still aborts actual retreat from constrained contact');
}
