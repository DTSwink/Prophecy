// Wrist branch regression: immutable profile reproduces the reported -40/-50 split.
const assert=require('node:assert/strict'),H=require('./holster'),F=require('./armfk'),R=require('./recovery');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),fixture=require('./tests/fk-wrist-profile.json');
const options=x=>{const o=structuredClone(fixture.parameters);o.bodyTargets.clear.spine[0]=x;return o;};
const wrist=m=>m.arm[2],report=[];
let previous=null,maxNeighbor=0;
for(let x=-35;x>=-55;x--){
 const m=H.prepare(data,setup,options(x));assert(m.completionTick,'S completion '+x);
 let travel=0;for(let i=m.o.startTick+1;i<m.frames.length&&m.frames[i].phase==='Reach';i++)travel+=H.angle(m.frames[i-1].pose[wrist(m)].q,m.frames[i].pose[wrist(m)].q);
 assert(travel<170,'wrist takes reversed arc '+x+': '+travel);
 const halfway=H.sample(m,(m.o.startTick+(m.plan.reachEndTick-m.o.startTick)*.5)/60).pose[wrist(m)];
 if(previous){const delta=H.angle(previous.q,halfway.q);maxNeighbor=Math.max(maxNeighbor,delta);assert(delta<5,'nearby spine edit reverses wrist '+x);}
 previous=halfway;report.push({x,reach:m.plan.reachEndTick,travel});
 if(x===-40)for(const f of fixture.goodReference){const now=m.frames[f.tick];assert(H.angle(f.hand.q,now.pose[wrist(m)].q)<1e-4);assert(R.length(R.sub(f.hand.p,now.pose[wrist(m)].p))<1e-6,'good trajectory altered');}
}
// Select a long wrist arc across the source-to-target 180° cut. Target and
// quaternion signs must be irrelevant, including with a rotated neutral basis.
let signCases=0;
for(const basis of [[0,0,0,1],R.qexp([.8,-.5,1.4])])for(const targetAngle of [-155,-150,-145]){
 const q=a=>R.qm(basis,R.qexp([0,a*Math.PI/180,0])),bone=q=>({q,p:[1,0,0]});
 const source=[bone(basis),bone(basis),bone(q(35))],target=[bone(basis),bone(basis),bone(q(targetAngle))],neutral=[bone(basis),bone(basis),bone(basis)];
 const dst=F.reachDestination(source,target,neutral),expected=F.reach(source,dst,.5)[2].q;
 assert(H.angle(expected,q((35+targetAngle)/2))<1e-5);
 for(let mask=0;mask<8;mask++){
  const a=structuredClone(source),b=structuredClone(target),n=structuredClone(neutral);
  if(mask&1)a[2].q=R.mul(a[2].q,-1);if(mask&2)b[2].q=R.mul(b[2].q,-1);if(mask&4)n[2].q=R.mul(n[2].q,-1);
  const d=F.reachDestination(a,b,n);assert(H.angle(F.reach(a,d,.5)[2].q,expected)<1e-5);assert(H.angle(F.reach(a,d,1)[2].q,b[2].q)<1e-5);signCases++;
 }
 const seconds=F.duration(source,target,100,60,neutral);assert(seconds>=Math.abs(targetAngle-35)/60,'timing used short arc');
}
let motionCases=0;
for(const motion of ['idle','walk','run'])for(const sheathe of [true,false])for(const noCheat of [true,false]){
 const o=options(-50);Object.assign(o,o[sheathe?'sheatheBody':'drawBody'],{motion,sheathe,noCheat});o.bodyTargets.clear.spine[0]=-50;
 const m=H.prepare(data,setup,o);assert(m.completionTick,'motion completion '+JSON.stringify({motion,sheathe,noCheat}));
 assert(m.frames.every(f=>f.pose.every(p=>[...p.p,...p.q].every(Number.isFinite))));motionCases++;
}
console.log(JSON.stringify({pass:true,maxNeighbor,signCases,motionCases,selected:report.filter(r=>[-40,-50].includes(r.x))},null,2));
