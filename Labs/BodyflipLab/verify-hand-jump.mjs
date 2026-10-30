import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),H=require('./hand-support.js'),F=require('./flight.js'),I=require('./idle.js'),W=require('./wrist.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),m),run=idle.motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const p=idle.sample(0),floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,20],.4),defaults=C.sanitize({mode:'idle',ramps:false,surfaceIK:false,supportAlpha:0}),dist=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),report=[],checks=[];
const check=(name,value)=>{assert(value,name);checks.push(name);};
let maxBoneError=0,maxPinError=0,minPalmGap=Infinity,maxJoin=0,maxWristViolation=0,samples=0,worstPin=null,worstJoin=null;
function make({surface=floor,hand='hand',pose=p,velocity=[0,0,0],tune={}}={}){
 const poseAt=t=>({...pose,points:pose.points.map(v=>R.add(v,R.mul(velocity,t)))}),prior=t=>({pose:poseAt(t),root:poseAt(t).points[0],phase:Math.hypot(...velocity)>0?'FALL':'IDLE',vy:velocity[1],airTime:Math.max(0,t)});
 return F.create(run,jumps,{...defaults,...tune},parents,reference,{hand,time:0,surface,poseAt,continueAt:prior,velocityAt:()=>velocity});
}
function inspect(label,f,expectPush=null){
 const pushed=Number.isFinite(f.jumpStart)&&(!f.bounce||f.bounce.didPush),l=f.support.leg;
 if(expectPush!==null&&pushed!==expectPush)console.log({label,scores:f.support.scores,posture:f.support.posture.amount,frames:f.support.frames.slice(0,3)});
 if(expectPush!==null)check(label+' result '+JSON.stringify({contact:f.contactTime,push:f.jumpStart,abort:f.abortTime,reason:f.failureReason,bounce:f.bounce?.limitReason}),pushed===expectPush);
 const end=Math.min(3,Number.isFinite(f.airStart)?f.airStart+.5:f.abortTime+.1);
 for(let t=0;t<=end;t+=1/240){
  const frame=f.sample(t),pose=frame.pose;checkFinite(pose,label,t);
  if(frame.phase==='SUPPORT'||frame.supportState==='PIN'){const wrist=l.wrist.inspect(pose.q[l.knee],pose.q[l.foot]);maxWristViolation=Math.max(maxWristViolation,wrist.ellipse-1,Math.abs(wrist.angle)-W.limits.twistMax);}
  const local=R.localize(pose.points,pose.q,parents),rest=R.localize(p.points,p.q,parents);
  for(let i=2;i<names.length;i++)maxBoneError=Math.max(maxBoneError,Math.abs(R.length(local.p[i])-R.length(rest.p[i])));
  if(frame.supportState==='PIN'){
   const contact=f.contactMotion.sample(t-f.contactTime,frame.root),error=dist(pose.points[l.foot],contact.foot);if(error>maxPinError){maxPinError=error;worstPin={label,t,error,phase:frame.phase,actual:pose.points[l.foot],target:contact.foot,reach:f.support.maxReach,distance:dist(pose.points[l.hip],contact.foot)};}
   const gap=Math.min(...H.corners(pose,l.foot,l.side).map(v=>R.dot(R.sub(R.add(pose.points[l.foot],v),f.surface.origin),f.surface.normal)));minPalmGap=Math.min(minPalmGap,gap);
  }
  samples++;
 }
 for(const t of [f.jumpStart,f.airStart,f.airStart+defaults.legBlend])if(Number.isFinite(t)){
  const a=f.sample(Math.max(0,t-1e-7)).pose,b=f.sample(t+1e-7).pose;
  for(let i=1;i<names.length;i++){const error=Math.max(dist(a.points[i],b.points[i]),angle(a.q[i],b.q[i]));if(error>maxJoin){maxJoin=error;worstJoin={label,t,bone:names[i],error,position:dist(a.points[i],b.points[i]),angle:angle(a.q[i],b.q[i]),release:f.airStart,push:f.jumpStart};}}
 }
 if(pushed){check(label+' no arrow before push',!f.pushDebug(f.jumpStart-1e-5));check(label+' three-frame arrow',!!f.pushDebug(f.jumpStart)&&!f.pushDebug(f.jumpStart+3/60));}
 const at=Number.isFinite(f.airStart)?f.airStart+.04:.1,seek=JSON.stringify(f.sample(at));f.sample(0);f.sample(20);check(label+' deterministic seek',JSON.stringify(f.sample(at))===seek);
 report.push({label,pushed,side:l.side,contact:f.contactTime,push:f.jumpStart,release:f.airStart,abort:f.abortTime,reason:f.failureReason,bodyBend:f.support.posture.amount,load:f.bounce?.loadDuration});
}
function checkFinite(p,label,t){assert(p.points.flat().every(Number.isFinite)&&p.q.flat().every(Number.isFinite),label+' finite '+t);}
for(const hand of ['hand','handL','handR'])inspect('idle floor '+hand,make({hand}),true);
const auto=make();check('Auto chooses nearer eligible hand after cone',auto.supportFoot===auto.support.scores.filter(s=>s.eligible).sort((a,b)=>a.distance-b.distance)[0].foot);
for(const bend of [.15,.6,1])inspect('bend '+bend,make({tune:{handBend:bend}}),true);
for(const loadMs of [0,200])inspect('load '+loadMs,make({tune:{loadMs}}),true);
for(const normal of [[0,1,0],[Math.SQRT1_2,Math.SQRT1_2,0],[-Math.SQRT1_2,Math.SQRT1_2,0],[0,0,-1]]){
 // Rotate the rig and its floor together. A plane 18 cm below the wrist cuts
 // through an upright source body's legs and is not a valid push fixture.
 const rotation=R.fromTo([0,1,0],normal),q=p.q.map(v=>R.qm(rotation,v)),pose={points:p.points.map(v=>R.rotate(rotation,v)),q,axes:q.map(R.toAxes)};
 const ground=S.rectangle('incline',[0,0,0],R.rotate(rotation,[1,0,0]),R.rotate(rotation,[0,0,1]),[-5,5,-5,20],.4);
 const rotated=make({surface:ground,pose,hand:'handL'}),pushed=Number.isFinite(rotated.jumpStart)&&(!rotated.bounce||rotated.bounce.didPush);
 // The existing grounded crouch drops along world Y. A laterally tilted rig
 // need not reach the plane; it must fail cleanly, without a fictitious push.
 inspect('incline '+normal,rotated,normal[1]===1?true:null);
 if(!pushed){check('Rotated floor miss aborts or releases without active push '+normal,Number.isFinite(rotated.abortTime)||rotated.bounce?.didPush===false);if(rotated.bounce)check('Rotated floor miss adds no active impulse '+normal,dist(rotated.bounce.released.v,rotated.bounce.frames.at(-1).v)<1e-12);}
 // This deliberately intersecting plane tests only immediate capture and its
 // initial orientation, not whole-body clearance or a physically valid push.
 const l=H.arm(p,names,'L'),near=R.add(p.points[l.foot],H.lowestOffset(p,l,normal)),u=R.unit(R.cross(normal,Math.abs(normal[1])<.9?[0,1,0]:[0,0,1])),v=R.cross(u,normal);
 const touching=S.rectangle('touch',near,u,v,[-2,2,-2,2]),f=make({surface:touching,hand:'handL'});
 check('Touching hand skips approach '+normal,f.contactTime===0);
 const before=f.sample(0).pose;check('No forced orientation snap at immediate capture '+normal,angle(before.q[l.foot],p.q[l.foot])<1e-8);
}
const slope=S.rectangle('slope',[0,0,.35],[1,0,0],[0,Math.SQRT1_2,Math.SQRT1_2],[-2,2,-2,2]);
inspect('front slope',make({surface:slope,hand:'handL'}),true);
const wall=S.rectangle('wall',[0,0,.55],[1,0,0],[0,1,0],[-2,2,0,3]);inspect('front wall',make({surface:wall}),true);
inspect('wall out of reach',make({surface:S.rectangle('far',[0,0,3],[1,0,0],[0,1,0],[-2,2,0,3])}),false);
inspect('no cone intersection',make({surface:S.rectangle('edge',[4,0,0],[1,0,0],[0,0,1],[0,.1,0,.1])}),false);
for(const speed of [100,400,800])inspect('approach speed '+speed,make({tune:{supportSpeed:speed}}),true);
inspect('descending floor',make({pose:{...p,points:p.points.map(v=>R.add(v,[0,.15,0]))},velocity:[0,-2,0]}));
// Cached real gait poses: no NN calls, including non-default source phases.
for(const gait of ['walk','run'])for(const time of [.1,.4,.7]){
 const motion=F.decodeNN(read('data/'+gait+'-default.json')),settings={...defaults,mode:gait==='run'?'jump':'walk',jumpEvents:[{id:'hand',time,pushWith:'hand'}],platforms:[S.platformRecord(floor)]};
 const seq=F.sequence(motion,jumps,settings,parents,reference),segment=seq.segments[0];
 // At this Run phase the palm lands behind the shoulder with only 2.7 mm
 // extension left. The old success relied on the root sinking through floor.
 const taut=gait==='run'&&(time===.1||time===.7);inspect(gait+' marker '+time,segment,!taut);
 if(taut)check('Taut running contact respects capsule/reach instead of borrowing jump height '+time,!segment.bounce||!segment.bounce.didPush&&['Reach limit','Capsule contact'].includes(segment.bounce.limitReason));
 if(taut&&segment.bounce)check('Failed hand push adds no active impulse '+time,dist(segment.bounce.released.v,segment.bounce.frames.at(-1).v)<1e-12);
 check(gait+' keeps advancing in support '+time,seq.sample(time+.05).root[2]>seq.sample(time).root[2]);
}
// Real shared capsule/timeline composition, without inference or saved-state writes.
const settings={...defaults,jumpEvents:[{id:'hand',time:.1,surface:'auto',pushWith:'hand'}],platforms:[S.platformRecord(floor)]},sequence=F.sequence(run,jumps,settings,parents,reference);
check('Timeline hand jump pushes',sequence.events[0].status==='Push');check('Capsule returns to locomotion',sequence.landings.length>0);
for(let t=0;t<=3;t+=1/60){const frame=sequence.sample(t);checkFinite(frame.pose,'timeline',t);check('Capsule does not fall through floor '+t,frame.root[1]>=-1e-5);}
check('Debug points to hand bone',sequence.sample(sequence.segments[0].jumpStart).supportBone===names.indexOf('hand_'+sequence.segments[0].supportFoot.toLowerCase()));
for(let t=.11;t<sequence.segments[0].airStart+defaults.legBlend;t+=1/120){const pose=sequence.sample(t).pose,l=sequence.segments[0].support.posture.freeArm,gap=Math.min(...H.corners(pose,l.foot,l.side).map(v=>R.add(pose.points[l.foot],v)[1]));check('Free hand clears floor during fold '+t,gap>=-2e-5);}
const wallSequence=F.sequence(run,jumps,{...settings,platforms:[S.platformRecord(floor),S.platformRecord(wall)]},parents,reference);
check('Nearest valid wall wins over floor',wallSequence.events[0].surfaceId==='wall'&&wallSequence.events[0].status==='Push');
for(const seq of [sequence,wallSequence])for(let t=0;t<1.5;t+=1/240){const frame=seq.sample(t),segment=seq.activeAt(t);if(frame.supportState==='PIN'){const contact=segment.contactMotion.sample(t-segment.contactTime,frame.root);check('Full capsule composition retains hand contact '+t,dist(frame.pose.points[segment.supportBone],contact.foot)<2e-5);}}
for(const mode of ['idle','spaceGym']){const zero=F.sequence(run,jumps,{...settings,mode,jumpEvents:[{id:'zero',time:.1,pushWith:'hand',jumpPercent:0}]},parents,reference);check('Zero percent still an action '+mode,zero.events[0].status===(mode==='spaceGym'?'Space':'Action'));check('Zero percent adds no impulse '+mode,dist(zero.sample(.2).root,zero.sample(.1).root)<1e-8);checkFinite(zero.sample(.2).pose,'zero',.2);}
const mixed=F.sequence(run,jumps,{...settings,jumpEvents:[{id:'hand',time:.1,pushWith:'hand'},{id:'foot',time:1.8,pushWith:'foot'}]},parents,reference);
check('Hand and foot markers coexist',mixed.segments.length===2&&mixed.segments[0].supportKind==='hand'&&mixed.segments[1].supportKind==='foot');
// Foot paths retain the saved pre-hand implementation exactly.
const legacy={};for(const name of ['support','bounce','flight']){const module={exports:{}};vm.runInNewContext(fs.readFileSync('Saved/BodyflipLab/HandJump/before-'+name+'.js','utf8'),{module,require:id=>legacy[id]||require(id)});legacy['./'+name+'.js']=module.exports;}const old=legacy['./flight.js'];
let footError=0;
for(const gait of [run,F.decodeNN(read('data/run-default.json')),F.decodeNN(read('data/walk-default.json'))])for(const loadMs of [0,100])for(const jumpFoot of ['Auto','L','R']){
 const settings={...defaults,loadMs,jumpFoot,runSeconds:1},a=old.create(gait,jumps,settings,parents,reference),b=F.create(gait,jumps,settings,parents,reference);
 check('Foot timing unchanged '+loadMs+jumpFoot,a.jumpStart===b.jumpStart&&a.release===b.release&&a.abortTime===b.abortTime);
 for(let t=0;t<3;t+=1/60){const pa=a.sample(t).pose,pb=b.sample(t).pose;footError=Math.max(footError,...pa.points.map((v,i)=>dist(v,pb.points[i])),...pa.q.map((v,i)=>angle(v,pb.q[i])));}
}
if(maxPinError>=2e-5||maxJoin>=.001)console.log({maxPinError,worstPin,minPalmGap,maxJoin,worstJoin,maxBoneError,footError});
check('Foot numerical regression',footError<1e-10);check('Pinned hand stays at contact',maxPinError<2e-5);check('Palm cannot penetrate while pinned',minPalmGap>-2e-5);check('No stretched body bones',maxBoneError<.008);check('No release or blend-end teleport',maxJoin<.001);check('Support wrists stay inside physical limits',maxWristViolation<1e-7);
check('Old saves default to feet',C.sanitizeJump({}).pushWith==='foot');check('Support choice persists',C.sanitize({jumpEvents:[{id:'x',time:1,pushWith:'handR'}]}).jumpEvents[0].pushWith==='handR');
const result={checks:checks.length,samples,maxBoneError,maxPinError,minPalmGap,maxJoin,maxWristViolation,footError,report};fs.writeFileSync(new URL('hand-jump-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
