import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),M=require('./mass.js'),H=require('./momentum.js'),F=require('./physical-flight.js');
const {names,parents}=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),reference=C.poseFromShared(JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url)))),rig=M.model(names,parents,reference),local=R.localize(reference.points,reference.q,parents),dt=1/240;
let checks=0,maxMomentumError=0,maxCOMError=0;const check=(name,yes)=>{assert(yes,name);checks++;},distance=(a,b)=>R.length(R.sub(a,b));
const vector={from:[0,0,0],to:[2,.4,-.3],begin:0,duration:0},zero={from:[0,0,0],to:[0,0,0],begin:0,duration:0},plan={referenceI:M.tensor(reference,rig),flip:vector,twist:zero};
const posed=t=>{const q=local.q.map(x=>x.slice());for(const name of ['upperarm_l','upperarm_r','thigh_l','thigh_r']){const i=names.indexOf(name);q[i]=R.qm(q[i],R.qexp([.1*Math.sin(t*4),.1*Math.cos(t*3)-.1,.15*Math.sin(t*2)]));}return R.fk({p:local.p,q},parents);};
const source=t=>{const turn=R.qexp(R.mul(vector.to,Math.max(0,t))),pose=M.rotateAboutCOM(posed(Math.max(0,t)),turn,rig);return {pose,root:pose.points[0],phase:'SPACE',spin:{q:turn,rotation:turn,spinPlan:plan}};};
for(const momentum3D of [true,false]){
 const seedTimes=[],seedSource=t=>{seedTimes.push(t);return source(t);},track=F.create(source,{start:0,settings:{momentum3D},names,parents,reference,gravity:0,seedSource});
 const initial=M.center(source(0).pose,rig),target=M.product(plan.referenceI,vector.to),axis=R.unit(vector.to);
 let before=source(0);
 for(let i=1;i<=120;i++){
  const frame=track.sample(i*dt),actual=H.momentum(before.pose,frame.pose,rig,dt),difference=R.sub(actual,target),error=momentum3D?R.length(difference):Math.abs(R.dot(difference,axis));
  maxMomentumError=Math.max(maxMomentumError,error);maxCOMError=Math.max(maxCOMError,distance(M.center(frame.pose,rig),initial));check('Final sampled momentum matches commanded target',error<.0002);
  if(i>1){const measuredCarrier=R.mul(R.qlog(R.qm(frame.spin.rotation,R.qinv(before.spin.rotation))),1/dt);check('Spin omega reports corrected carrier motion',distance(frame.spin.omega,measuredCarrier)<1e-10);}
  before=frame;
 }
 check('Seed reads remain before release',seedTimes.every(t=>t<0));
 const fractional=.301234,stored=JSON.stringify(track.sample(fractional));track.sample(.7);track.sample(.01);check('Fractional backward seek is deterministic',JSON.stringify(track.sample(fractional))===stored);
 const correction=track.sample(.3);check('Carrier omega includes articulation reaction',distance(correction.spin.omega,vector.to)>1e-4);
 check('Only requested timeline is cached',track.ticks<=169);
}
check('COM remains fixed in zero gravity',maxCOMError<1e-10);
const noSpin=t=>({pose:posed(Math.max(0,t)),root:reference.points[0],phase:'SPACE'});
const noCommand=F.create(noSpin,{start:0,settings:{momentum3D:false},names,parents,reference,gravity:0});
let before=noSpin(0);for(let i=1;i<50;i++){const frame=noCommand.sample(i*dt);check('Zero command still balances all axes',frame.physical.axis===null&&R.length(H.momentum(before.pose,frame.pose,rig,dt))<.0002);before=frame;}
check('Zero-command articulation produces carrier reaction',R.length(R.qlog(before.physical.rotation))>1e-5);
const noInertiaCommand=F.create(noSpin,{start:0,settings:{momentum3D:false,spinInertia:0},names,parents,reference,gravity:0});
check('Zero inertia multiplier retains articulation reaction',distance(R.qlog(noInertiaCommand.sample(.3).physical.rotation),R.qlog(noCommand.sample(.3).physical.rotation))<1e-12);
const retainedAxisSource=t=>({...noSpin(t),spin:{spinAxis:[1,0,0],q:[0,0,0,1],rotation:[0,0,0,1],spinPlan:{...plan,flip:zero,twist:zero}}});
const retainedAxis=F.create(retainedAxisSource,{start:0,settings:{momentum3D:false},names,parents,reference,gravity:0}),stopped=retainedAxis.sample(.3);
check('Zero command retains the previous fixed axis when supplied',distance(stopped.physical.axis,[1,0,0])<1e-12);
check('Stopping does not add a transverse correction',R.length(R.cross(R.qlog(stopped.physical.rotation),[1,0,0]))<1e-12);
const moving=t=>({...noSpin(0),pose:{...reference,points:reference.points.map(p=>R.add(p,[2*t,3*t,-t]))},root:R.add(reference.points[0],[2*t,3*t,-t])});
const falling=F.create(moving,{start:0,settings:{momentum3D:true},names,parents,reference,gravity:10,cap:2,velocityImpulse:[0,1,0]});
const initial=M.center(reference,rig),one=falling.sample(1),com=M.center(one.pose,rig);check('Ballistic COM includes explicit jump impulse and fall cap',distance(com,R.add(initial,[2,-.2,-1]))<1e-8);
check('Terminal velocity is capped',distance(one.physical.velocity,[2,-2,-1])<1e-8);
const raw=moving(1),delta=R.sub(com,M.center(raw.pose,rig));check('Root gets the same translation as the body',distance(one.root,R.add(raw.root,delta))<1e-8);
let launchCalls=0;
const launched=F.create(moving,{start:0,settings:{},names,parents,reference,gravity:10,balance:false,releaseVelocity:v=>{launchCalls++;return [v[0],9,v[2]];}}),launchFrame=launched.sample(.5);
check('Gameplay launch replaces only the commanded component',distance(launchFrame.physical.velocity,[2,4,-1])<1e-8);
check('Gameplay launch starts at the contact COM',distance(launched.state(0).com,initial)<1e-10);
check('Translation-only flight keeps every authored rotation',JSON.stringify(launchFrame.pose.q)===JSON.stringify(moving(.5).pose.q));
launched.sample(1);launched.sample(.2);check('Launch impulse is applied once across forward and reverse seeks',launchCalls===1);
// A short push is still accelerating sharply immediately before release.
// Its final velocity, not the average over the last integration tick, owns
// free flight. Also cover oblique pushes and passive falling releases.
const launchChecks=[];
for(const [label,velocity,acceleration,jerk] of [
 ['short push',[0,4.6,5],[0,700,0],[0,-45000,0]],
 ['inclined push',[3,3,5],[450,450,0],[10000,-20000,0]],
 ['falling release',[1,-4,2],[0,-9.81,0],[0,0,0]]
]){
 const seedTimes=[],seedSource=t=>{seedTimes.push(t);const offset=R.add(R.mul(velocity,t),R.add(R.mul(acceleration,t*t/2),R.mul(jerk,t*t*t/6)));return {...moving(0),pose:{...reference,points:reference.points.map(p=>R.add(p,offset))},root:R.add(reference.points[0],offset)};};
 const track=F.create(source,{start:0,settings:{},names,parents,reference,seedSource}),seed=track.state(0),time=Math.max(.1,velocity[1]/9.81),frame=track.sample(time),expected=R.add(initial,R.add(R.mul(velocity,time),[0,-4.905*time*time,0]));
 const speedError=distance(seed.velocity,velocity),positionError=distance(frame.physical.com,expected);
 check(label+' retains the final contact velocity',speedError<.0003);
 check(label+' uses only completed contact samples',seedTimes.every(t=>t<0));
 check(label+' keeps the ballistic height and horizontal travel',positionError<.0002);
 launchChecks.push({label,speedError,positionError});
}
const predictor=[];
for(const momentum3D of [true,false]){
 const common={start:0,settings:{momentum3D},names,parents,reference,gravity:0},fine=F.create(source,common),coarse=F.create(source,{...common,stepSeconds:1/60}),hit=.6137;
 const a=fine.sample(hit),b=coarse.sample(hit),angle=R.length(R.qlog(R.qm(a.pose.q[1],R.qinv(b.pose.q[1]))))*180/Math.PI;
 check('60Hz predictor agrees with240Hz hit orientation for the smooth fixture',angle<1);
 const stored=JSON.stringify(coarse.sample(hit));coarse.sample(.9);coarse.sample(.1);check('60Hz fractional seek is deterministic',JSON.stringify(coarse.sample(hit))===stored);
 const run=F.create(source,{...common,stepSeconds:1/60}),begun=performance.now();for(let i=1;i<=120;i++)run.sample(i/60);const msPerFrame=(performance.now()-begun)/120;
 predictor.push({momentum3D,hit,orientationDifferenceDegrees:angle,generatedFrames:120,msPerFrame});
}
assert.throws(()=>F.create(source,{start:0,settings:{},names,parents,reference,stepSeconds:0}),/positive/);checks++;
// Analytic varying-inertia fixture: body centres contract radially, producing
// no articulation angular momentum. Body rotations share a single world axis.
const axis=[1,0,0],speed=1.5,centers=M.bodies(reference,rig).map(b=>b.center),center=M.center(reference,rig),radialPlan={referenceI:M.tensor(reference,rig),flip:{...zero,to:R.mul(axis,speed)},twist:zero};
function radial(t){
 const time=Math.max(0,t),scale=1-.3*Math.min(1,time/.5),turn=R.qexp(R.mul(axis,speed*time)),q=reference.q.map((v,i)=>i?R.qm(turn,v):v),points=reference.points.map(p=>p.slice());
 for(let k=0;k<rig.length;k++){const b=rig[k],world=R.add(center,R.rotate(turn,R.mul(R.sub(centers[k],center),scale)));points[b.i]=R.sub(world,R.rotate(q[b.i],b.offset));}
 return {pose:{points,q},root:points[0],spin:{q:turn,rotation:turn,spinPlan:radialPlan}};
}
const inertiaMeaning=[];
for(const spinInertia of [0,.5,1]){
 const track=F.create(radial,{start:0,settings:{momentum3D:false,spinInertia},names,parents,reference,gravity:0}),a=track.sample(.6-dt),b=track.sample(.6),measured=R.dot(R.qlog(R.qm(b.pose.q[1],R.qinv(a.pose.q[1]))),axis)/dt;
 const currentI=M.moment(M.tensor(b.pose,rig),axis),referenceI=M.moment(radialPlan.referenceI,axis),expected=speed*((1-spinInertia)+spinInertia*referenceI/currentI);
 check('Spin inertia interpolates speed control and angular momentum control',Math.abs(measured-expected)<.001);
 inertiaMeaning.push({spinInertia,measured,expected,currentI,referenceI});
}
check('Compaction increases spin only when inertia influence is enabled',inertiaMeaning[2].measured>1.7*inertiaMeaning[0].measured);
const speedControlled3D=F.create(radial,{start:0,settings:{momentum3D:true,spinInertia:0},names,parents,reference,gravity:0}),prior3D=speedControlled3D.sample(.6-dt),after3D=speedControlled3D.sample(.6);
const angular3D=R.mul(R.qlog(R.qm(after3D.pose.q[1],R.qinv(prior3D.pose.q[1]))),1/dt);
check('Zero inertia multiplier keeps commanded speed in full3D',distance(angular3D,R.mul(axis,speed))<.002);
const frameBudget=[];
for(const rate of [60,240])for(const momentum3D of [true,false]){
 const track=F.create(source,{start:0,settings:{momentum3D},names,parents,reference,gravity:0,stepSeconds:1/rate}),begun=performance.now();for(let i=1;i<=rate;i++)track.sample(i/rate);
 const msPerStep=(performance.now()-begun)/rate;frameBudget.push({rate,momentum3D,msPerStep,msPer60HzFrame:msPerStep*rate/60});
}
console.log(JSON.stringify({passed:true,checks,maxMomentumError,maxCOMError,launchChecks,predictor,inertiaMeaning,frameBudget},null,2));
