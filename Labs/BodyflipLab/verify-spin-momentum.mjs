import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./spin.js'),M=require('./mass.js'),F=require('./flight.js'),G=require('./space-gym.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),rig=M.model(names,parents,reference),settings=C.sanitize({spinInertia:1,spinLag:0});
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,R.dot(a,b)/(R.length(a)*R.length(b)))))*180/Math.PI;
let checks=0;const check=(label,condition)=>{assert(condition,label);checks++;};
// Measure the applied rotation independently from its quaternion trajectory.
// This verifies controlled axial inertia, NOT full torque-free conservation.
function measured(motion,t){const h=1e-5;return R.mul(R.qlog(R.qm(motion.state(t+h).q,R.qinv(motion.state(t-h).q))),.5/h);}
const local=R.localize(reference.points,reference.q,parents),joints=require('./joint-rig.js').create(names,parents,reference);
function moving(t){const pose={p:local.p.map(p=>p.slice()),q:local.q.map(q=>q.slice())};for(const j of joints.joints.filter(j=>j.hinge)){pose.q[j.i]=R.qm(R.qexp(R.mul(j.axisLocal,.5+.35*Math.sin(t*4))),j.bind);}return R.fk(pose,parents);}
const reports=[];
for(const articulated of [false,true])for(const lag of [0,.6])for(const axis of [0,3,7])for(const [flip,twist] of [[350,0],[-300,1400],[0,1400]]){
 const source=t=>({pose:articulated?moving(t):reference,phase:'SPACE'}),motion=S.create(source,{event:{spinVersion:2,flip,twist,turnAxis:axis,instantSpin:true},settings:{...settings,spinLag:lag},names,parents,reference});
 let maxAngle=0,maxRelative=0;const initial=motion.state(0),axisWorld=initial.spinAxis,L=initial.axialMomentum;
 for(let f=1;f<60;f++){const t=(f+.37)/60,s=motion.sample(t),w=measured(motion,t),actual=M.moment(M.tensor(s.pose,rig),axisWorld)*R.dot(w,axisWorld);maxAngle=Math.max(maxAngle,angle(w,axisWorld));maxRelative=Math.max(maxRelative,Math.abs(actual-L)/L);check('Command axis remains fixed',distance(s.spin.spinAxis,axisWorld)<1e-9);check('COM remains at source COM',distance(M.center(s.pose,rig),M.center(source(t).pose,rig))<1e-9);}
 check('Measured rotation has no invented twist',maxAngle<.00001);check('Measured axial inertia balance within integration error',maxRelative<.02);
 const p=JSON.stringify(motion.sample(.4));motion.sample(.1);check('Backward seek deterministic',p===JSON.stringify(motion.sample(.4)));
 reports.push({articulated,lag,axis,flip,twist,maxAngle,maxRelative});
}
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),first={id:'first',time:0,jumpPercent:0,spinVersion:2,flip:-300,twist:1400,instantSpin:true},keep={id:'keep',time:.35,jumpPercent:0,spinVersion:2};
const gym=events=>G.sequence({names,poses:[reference]},jumps,{...settings,spinLag:.6,mode:'spaceGym'},parents,events,null,reference);
const whole=gym([first]),split=gym([first,keep]);let keepError=0;
for(const t of [.35,.4,.6,.8]){const a=whole.sample(t),b=split.sample(t);keepError=Math.max(keepError,...a.pose.points.map((p,i)=>distance(p,b.pose.points[i])));check('Keep preserves world command',distance(a.spin.spinAxis,b.spin.spinAxis)<1e-9);}
check('Keep preserves displayed motion',keepError<.003);
const second={...first,id:'second',time:.4,flip:350,twist:-200,turnDelay:.1,instantSpin:false,turnIn:.2,turnOut:.2},changed=gym([first,second]);
check('Delay preserves previous axis',distance(changed.sample(.49).spin.spinAxis,whole.sample(.49).spin.spinAxis)<1e-9);
check('Ramp has no axis discontinuity',distance(changed.sample(.5-1e-7).spin.spinAxis,changed.sample(.5+1e-7).spin.spinAxis)<1e-6);
check('New command settles to fixed world axis',distance(changed.sample(.75).spin.spinAxis,changed.sample(1).spin.spinAxis)<1e-9);
const stopped=gym([first,{...first,id:'stop',time:.4,flip:0,twist:0}]);check('Explicit zero stops rotation',R.length(stopped.sample(.5).spin.omega)<1e-9);
for(const turnDelay of [.1124994119,.2]){const spec={spinVersion:2,flip:350,twist:0,instantSpin:true},source=()=>({pose:reference}),args={settings:{...settings,spinLag:.6},names,parents,reference};const a=S.create(source,{...args,event:spec}),b=S.create(source,{...args,event:{...spec,turnDelay}});for(const age of [.01,.1,.3,.6]){const x=a.state(age),y=b.state(turnDelay+age);check('Delayed activation cannot inject sideways spin',R.length(R.cross(y.omega,C.flipAxis(0)))<1e-9);check('Delayed recoil preserves same launch command',Math.abs(x.axialMomentum-y.axialMomentum)<1e-8);}}
const result={passed:true,checks,keepError,maxAngle:Math.max(...reports.map(r=>r.maxAngle)),maxRelative:Math.max(...reports.map(r=>r.maxRelative)),reports};
console.log(JSON.stringify(result,null,2));
