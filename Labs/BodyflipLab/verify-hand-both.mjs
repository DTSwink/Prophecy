// Historical contact/COM fixtures use equal tier times to retain their original loading.
// Two-hand support uses frozen local motions. No NN, server or desktop access.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),H=require('./hand-support.js'),F=require('./flight.js'),W=require('./wrist.js'),I=require('./idle.js'),K=require('./capsule.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),bytes=n=>{const b=fs.readFileSync(new URL(n,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),manifest);
const motions={idle:idle.motion(),walk:F.decodeNN(read('data/walk-default.json')),run:F.decodeNN(read('data/run-default.json'))};
const {add,sub,mul,dot,length,qm,qinv,qlog}=R,distance=(a,b)=>length(sub(a,b)),angle=(a,b)=>length(qlog(qm(a,qinv(b)))),reports=[];
const base=C.sanitize({loadYMs:100,loadFullMs:100,mode:'idle',motion:'kinematic',ramps:false,surfaceIK:false,supportAlpha:0}),floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,20],.4);
function forearmGap(a,b,surface){
 const at=t=>{const v=add(a,mul(sub(b,a),t));return distance(v,surface.closest(v));};let lo=0,hi=1;
 for(let i=0;i<20;i++){const a=lo+(hi-lo)/3,b=hi-(hi-lo)/3;if(at(a)<at(b))hi=b;else lo=a;}
 return Math.min(at(0),at(1),at((lo+hi)/2))-.048;
}
function exportPoses(file,sequence,segment,start,end){
 const times=Array.from({length:Math.ceil((end-start)*60)+1},(_,i)=>start+i/60);for(const h of segment.support.hands||[])times.push(segment.supportStart+h.contactDelay);times.sort((a,b)=>a-b);
 fs.writeFileSync(new URL('../../Saved/BodyflipLab/HandReview/'+file,import.meta.url),JSON.stringify({names,parents,reference,frames:times.filter(t=>t<=end).map(time=>({time,...sequence.sample(time)})),timing:{paired:!!segment.support.paired,hands:segment.support.hands?.map(h=>({side:h.leg.side,contact:segment.supportStart+h.contactDelay})),contact:segment.contactTime,jump:segment.jumpStart,release:segment.airStart}}));
}
function bank(){
 const meta=read('data/walk-drawn-phases.json'),count=Math.ceil(5*meta.fps)+2,width=3+meta.names.length*12,b=Buffer.alloc(count*width*4),fd=fs.openSync(new URL('data/walk-drawn-phases.bin',import.meta.url),'r');try{assert.equal(fs.readSync(fd,b,0,b.length,0),b.length);}finally{fs.closeSync(fd);}
 const roots=[],poses=[];for(let f=0;f<count;f++){const row=Array.from({length:width},(_,i)=>b.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}return F.decodeNN({...meta,duration:5,roots,poses});
}
function audit(label,segment,sample,end){
 const support=segment.support,limbs=support.limbs||[support.leg],start=segment.supportStart,report={label,paired:!!support.paired,pushed:Number.isFinite(segment.jumpStart)&&(!segment.bounce||segment.bounce.didPush),reason:segment.failureReason||segment.bounce?.limitReason||null,contact:segment.contactTime,release:segment.airStart,wait:support.hands?.map(h=>h.wait),pin:0,stretch:0,limit:0,twist:0,deviation:0,palm:Infinity,forearm:Infinity,seam:0,rotationSeam:0,samples:0};
 for(let t=start;t<=end;t+=1/120)for(const time of [t,t+1/480]){
  if(time>end)continue;const frame=sample(time),p=frame.pose;assert(p.points.flat().every(Number.isFinite)&&p.q.flat().every(Number.isFinite),label+' finite');report.samples++;
  const pinned=frame.supportState==='PIN'?segment.contactMotion.sample(time-segment.contactTime,frame.root):null,contacts=pinned?(pinned.hands||[{...pinned,leg:support.leg}]):frame.phase==='SUPPORT'?(support.sample(time-start,frame.root).hands||[]).filter(c=>c.pinned):[];
  for(const l of limbs){
   if(frame.phase!=='SUPPORT'&&frame.supportState!=='PIN')continue;
   const a=l.wrist.inspect(p.q[l.knee],p.q[l.foot]),initial=W.decompose(W.clampConstraint(l.wristStart));report.limit=Math.max(report.limit,a.ellipse-1,Math.abs(a.angle)-W.limits.twistMax);report.twist=Math.max(report.twist,Math.abs(a.angle-initial.angle));report.deviation=Math.max(report.deviation,Math.abs(a.swing[2]-initial.swing[2]));
   const c=contacts.find(c=>c.leg===l);if(!c)continue;
   const pin=distance(p.points[l.foot],c.foot);if(pin>report.pin){report.pin=pin;report.pinWorst={time,phase:frame.phase,side:l.side};}report.stretch=Math.max(report.stretch,distance(p.points[l.hip],c.foot)-l.reach*base.supportReach);
   const gap=v=>dot(sub(v,segment.surface.origin),segment.surface.normal);report.palm=Math.min(report.palm,...H.corners(p,l.foot,l.side).map(v=>gap(add(p.points[l.foot],v))));const forearm=forearmGap(p.points[l.knee],p.points[l.foot],segment.surface);if(forearm<report.forearm){report.forearm=forearm;report.forearmWorst={time,phase:frame.phase,side:l.side};}
  }
 }
 const seams=[start,segment.contactTime,segment.jumpStart,segment.airStart,...(support.hands||[]).map(h=>start+h.contactDelay)];
 for(const t of seams)if(Number.isFinite(t)&&t<=end){const a=sample(t-1e-7).pose,b=sample(t+1e-7).pose;for(let i=1;i<names.length;i++){const d=distance(a.points[i],b.points[i]);if(d>report.seam){report.seam=d;report.seamWorst={time:t,bone:names[i]};}report.rotationSeam=Math.max(report.rotationSeam,angle(a.q[i],b.q[i]));}}
 const at=(start+end)/2,expected=JSON.stringify(sample(at));sample(end);sample(start);report.deterministic=JSON.stringify(sample(at))===expected;
 reports.push(report);console.log(JSON.stringify(report));return report;
}
for(const gait of ['idle','walk','run']){
 const time=gait==='run'?.4:.1,settings={...base,mode:gait==='run'?'jump':gait,platforms:[S.platformRecord(floor)],jumpEvents:[{id:'both',time,pushWith:'handBoth'}]},seq=F.sequence(motions[gait],jumps,settings,parents,reference,null,null,{horizon:1.1}),seg=seq.segments[0];
 audit(gait+' floor',seg,t=>seq.sample(t),Math.min(1.1,Number.isFinite(seg.airStart)?seg.airStart+.15:seg.abortTime+.03));
 if(gait==='walk')exportPoses('both-ground-poses.json',seq,seg,.08,.8);
}
for(const [label,n,z] of [['slope',[0,Math.SQRT1_2,-Math.SQRT1_2],.35],['wall',[0,0,-1],.55]]){
 const raw=idle.sample(0),u=[1,0,0],surface=S.rectangle(label,[0,0,z],u,R.cross(u,n),[-2,2,-2,2]);
 // Match the real carrier's initial placement before the marker. Raw idle
 // export root is 0.63 mm below floor; resolving it only during LOAD would
 // manufacture a contact seam unrelated to the two-hand mechanism.
 const delta=label==='wall'?sub(K.move(raw.points[0],[0,0,0],[floor,surface]).root,raw.points[0]):[0,0,0],p={...raw,points:raw.points.map(v=>add(v,delta))},context={hand:'handBoth',time:0,surface,poseAt:()=>p,continueAt:()=>({pose:p,root:p.points[0],phase:'IDLE',speed:0,vy:0,airTime:0}),velocityAt:()=>[0,0,0]},seg=F.create(motions.idle,jumps,base,parents,reference,{...context,...(label==='wall'?{surfaces:[floor,surface]}:{})});
 audit(label,seg,t=>seg.sample(t),Math.min(.8,Number.isFinite(seg.airStart)?seg.airStart+.12:seg.abortTime+.03));
 if(label==='wall'){
  // Without a floor the same upright pose falls before both hands can settle;
  // it must preserve the reachable Auto hand rather than stretch the first pin.
  const unsupportedWall=S.rectangle('unsupported-wall',[0,0,.55],u,R.cross(u,n),[-2,2,-2,2]),unsupported=F.create(motions.idle,jumps,base,parents,reference,{...context,surface:unsupportedWall}),r=audit('unsupported wall fallback',unsupported,t=>unsupported.sample(t),Math.min(.8,Number.isFinite(unsupported.airStart)?unsupported.airStart+.12:unsupported.abortTime+.03));r.expectFallback=true;
 }
}
const savedSettings={...base,mode:'walk',surfaceIK:true,supportAlpha:1,attack:'slashLD',jumpEvents:[{id:'first',time:56/60,surface:'floor',pushWith:'foot',flip:90},{id:'hand',time:1.8,surface:'auto',pushWith:'handBoth',jumpPercent:50}],platforms:[{id:'floor',position:[0,-.2,-.5599910537770252],size:[3.6,.4,66.20677485127891],rotation:[0,0,0,1]}]};
const saved=F.sequence(bank(),jumps,savedSettings,parents,reference,null,null,{horizon:2.55}),savedSegment=saved.segments[1];
audit('saved 90-degree flip, 50 percent',savedSegment,t=>saved.sample(t),Math.min(2.55,Number.isFinite(savedSegment.airStart)?savedSegment.airStart+.15:savedSegment.abortTime+.03));
exportPoses('both-poses.json',saved,savedSegment,1.75,2.35);
// A side-bounded floor admits one cone, so Both must be exactly the Auto path.
const narrow=S.rectangle('narrow',[0,0,0],[1,0,0],[0,0,1],[.3,2,-5,20]),pose=idle.sample(0),fallbackContext={time:0,surface:narrow,poseAt:()=>pose,continueAt:()=>({pose,root:pose.points[0],phase:'IDLE',speed:0,vy:0,airTime:0}),velocityAt:()=>[0,0,0]},fallback=F.create(motions.idle,jumps,base,parents,reference,{...fallbackContext,hand:'handBoth'}),auto=F.create(motions.idle,jumps,base,parents,reference,{...fallbackContext,hand:'hand'});
const fallbackReport=audit('one cone fallback',fallback,t=>fallback.sample(t),Math.min(.8,Number.isFinite(fallback.airStart)?fallback.airStart+.12:fallback.abortTime+.03));fallbackReport.expectFallback=true;
let fallbackDifference=0;for(let t=0;t<.8;t+=1/60){const a=fallback.sample(t).pose,b=auto.sample(t).pose;for(let i=0;i<names.length;i++)fallbackDifference=Math.max(fallbackDifference,distance(a.points[i],b.points[i]),angle(a.q[i],b.q[i]));}console.log(JSON.stringify({fallbackDifference}));assert(fallbackDifference<1e-10,'Unreachable second hand preserves the old Auto path');
const edge=S.rectangle('edge',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,2.3],.4),edgeSettings={...base,mode:'jump',platforms:[S.platformRecord(edge)],jumpEvents:[{id:'edge',time:.4,pushWith:'handBoth'}]},edgeSequence=F.sequence(motions.run,jumps,edgeSettings,parents,reference,null,null,{horizon:.8}),edgeSegment=edgeSequence.segments[0],edgeReport=audit('past finite edge',edgeSegment,t=>edgeSequence.sample(t),edgeSegment.abortTime+.03);edgeReport.expectFallback=true;edgeReport.expectMiss=true;
assert.equal(edgeReport.reason,'Distance growing','Two-hand request retains real finite-edge retreat failure');
if(process.env.PAIR_AUDIT_ONLY!=='1')for(const r of reports){
 assert(r.paired===!r.expectFallback,r.label+' uses the feasible contact count');assert(r.pushed===!r.expectMiss,r.label+' shares one push only with valid contacts');assert(r.pin<3e-5,r.label+' preserves both contacts');assert(r.stretch<3e-5,r.label+' neither arm stretches');assert(r.limit<1e-7,r.label+' wrists within Jolt bounds');assert(r.twist<1e-5&&r.deviation<1e-5,r.label+' no new wrist twist/deviation');assert(r.palm>=-1e-6&&r.forearm>=-1e-6,r.label+' palm/forearm outside surface');assert(r.seam<.001&&r.rotationSeam<.003,r.label+' continuous contact/release');assert(r.deterministic,r.label+' deterministic seeking');
}
