import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),O=require('./spin.js'),M=require('./mass.js'),J=require('./joint-rig.js'),F=require('./flight.js'),G=require('./space-gym.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),rig=M.model(names,parents,reference),joints=J.create(names,parents,reference),checks=[];
const settings=C.sanitize({...C.defaults,spinLag:0,spinInertia:0}),source=()=>({pose:reference,root:reference.points[0],phase:'SPACE'}),event={instantSpin:true,spinVersion:2,flip:350,twist:0,turnIn:1,turnOut:1,turnDelay:.0713};
const dist=(a,b)=>R.length(R.sub(a,b)),rotationDist=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
function check(name,v){assert(v,name);checks.push(name);}
const motion=O.create(source,{event,settings,names,parents,reference,commandTime:.1337}),begin=motion.begin;
for(const dt of [-.002,-1e-6,0,1e-6,.002,.1]){
 const s=motion.sample(begin+dt).spin;
 check('Exact command boundary '+dt,Math.abs(s.target.flip-(dt<0?0:350))<1e-8);
 check('No pre-echo, exact integrated angle '+dt,Math.abs(s.flip-Math.max(0,dt)*350)<1e-7);
}
check('Angle continuous at instantaneous speed change',rotationDist(motion.state(begin-1e-8).q,motion.state(begin+1e-8).q)<1e-6);
check('Instant mode does not overwrite marker tuning',C.sanitizeJump(event).turnIn===1&&C.sanitizeJump(event).turnOut===1);
const reports=[];
for(const axis of [0,2,3,6,9])for(const [flip,twist] of [[350,0],[-350,0],[0,350],[720,720]]){
 const settingsLag={...settings,spinLag:.6},spec={instantSpin:true,spinVersion:2,flip,twist,turnAxis:axis,turnDelay:.0713},soft=O.create(source,{event:spec,settings:settingsLag,names,parents,reference}),hard=O.create(source,{event:spec,settings,names,parents,reference});
 let maxOffset=0,maxLimit=0,maxCom=0,maxAnchor=0;
 for(let f=0;f<=75;f++){
  const t=f/60,p=soft.sample(t).pose,q=hard.sample(t).pose;
  check('Finite pose '+axis+'/'+flip+'/'+twist+'/'+f,p.points.flat().concat(p.q.flat()).every(Number.isFinite));
  maxOffset=Math.max(maxOffset,...p.points.slice(1).map((p,i)=>dist(p,q.points[i+1])));maxCom=Math.max(maxCom,dist(M.center(p,rig),M.center(reference,rig)));
  for(const j of joints.inspect(p)){maxLimit=Math.max(maxLimit,j.angularError);maxAnchor=Math.max(maxAnchor,j.anchorError);}
  check('Does not slow target spin '+axis+'/'+flip+'/'+twist+'/'+f,Math.abs(soft.sample(t).spin.flip-hard.sample(t).spin.flip)<1e-6);
 }
 check('Visible, bounded recoil '+axis+'/'+flip+'/'+twist,maxOffset>.005&&maxOffset<.32);
 check('COM fixed '+axis+'/'+flip+'/'+twist,maxCom<1e-10);
 check('Jolt limits and bone lengths '+axis+'/'+flip+'/'+twist,maxLimit<1e-8&&maxAnchor<1e-9);
 check('Recoil settles '+axis+'/'+flip+'/'+twist,dist(soft.sample(1.25).pose.points[7],hard.sample(1.25).pose.points[7])<1e-5);
 const capture=JSON.stringify(soft.sample(.2));soft.sample(2);soft.sample(.05);check('Deterministic seek '+axis+'/'+flip+'/'+twist,capture===JSON.stringify(soft.sample(.2)));
 reports.push({axis,flip,twist,maxOffset,maxCom,maxLimit,maxAnchor});
}
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),setup={...settings,spinLag:.6,mode:'spaceGym'};
const first={id:'spin',time:0,jumpPercent:0,instantSpin:true,spinVersion:2,flip:350,twist:120},keep={id:'keep',time:.05,jumpPercent:0,instantSpin:true,spinVersion:2};
const whole=G.sequence({names,poses:[reference]},jumps,setup,parents,[first],null,reference),split=G.sequence({names,poses:[reference]},jumps,setup,parents,[first,keep],null,reference);
let keepError=0;for(const t of [.05,.06,.1,.15,.3,.5]){const a=whole.sample(t),b=split.sample(t);keepError=Math.max(keepError,...a.pose.points.map((p,i)=>dist(p,b.pose.points[i])));}
check('Keep does not repeat or discard recoil',keepError<.002);
const stop={...first,id:'stop',time:.3337,flip:0,twist:0},stopped=G.sequence({names,poses:[reference]},jumps,setup,parents,[first,stop],null,reference);
check('Instant explicit zero brakes immediately',stopped.sample(stop.time).spin.target.flip===0&&stopped.sample(stop.time).spin.target.twist===0);
check('Stop angle is retained',rotationDist(stopped.sample(.4).spin.rotation,stopped.sample(.8).spin.rotation)<1e-8);
check('Brake pose is continuous',Math.max(...stopped.sample(stop.time-1e-7).pose.points.map((p,i)=>dist(p,stopped.sample(stop.time+1e-7).pose.points[i])))<1e-4);
const inertial=O.create(source,{event:{instantSpin:true,spinVersion:2,flip:350,twist:0,turnDelay:.03},settings:{...settings,spinInertia:1,spinLag:.6},names,parents,reference});
for(const t of [.04,.08,.15,.4]){
 const f=inertial.sample(t),actual=M.moment(M.tensor(f.pose,rig),f.spin.axis),neutral=M.moment(M.tensor(reference,rig),C.flipAxis(0));
 check('Inertia uses the recoil pose '+t,Math.abs(f.spin.flipScale-neutral/actual)<1e-9);
}
check('New settings sanitize and persist',C.sanitize({spinLag:2}).spinLag===1&&C.sanitizeJump(C.sanitizeJump({instantSpin:true})).instantSpin);
check('Old settings retain their behavior',C.sanitizeJump({}).instantSpin===false&&C.sanitize({}).spinLag===0);
const mixed=G.sequence({names,poses:[reference]},jumps,settings,parents,[{...first,flip:120,twist:0},{...first,id:'smooth',time:1,flip:240,twist:0,turnIn:1,instantSpin:false}],null,reference);
check('Instant first marker reaches its speed',mixed.sample(.01).spin.target.flip===120);
check('Next unchecked marker ramps independently',mixed.sample(1).spin.target.flip===120&&mixed.sample(1.2).spin.target.flip>120&&mixed.sample(1.2).spin.target.flip<240);
const migrated=C.sanitize({instantSpin:true,jumpEvents:[{id:'a',time:0},{id:'b',time:1,instantSpin:false}]});
check('Legacy global preference migrates once with explicit overrides',migrated.jumpEvents[0].instantSpin&&!migrated.jumpEvents[1].instantSpin&&!('instantSpin' in migrated)&&JSON.stringify(C.sanitize(migrated))===JSON.stringify(migrated));
console.log(JSON.stringify({passed:true,checks:checks.length,keepError,reports},null,2));
