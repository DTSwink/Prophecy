import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),M=require('./mass.js'),O=require('./spin.js'),F=require('./flight.js'),G=require('./space-gym.js');
const manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),{names,parents}=manifest,reference=C.poseFromShared(manifest),rig=M.model(names,parents,reference),jumps=['jumps.json','jumps-standing.json'].flatMap(file=>JSON.parse(fs.readFileSync(new URL('data/'+file,import.meta.url))).clips).map(F.decodeJump);
const settings=C.sanitize({...C.defaults,spinInertia:0}),source=()=>({pose:reference,root:reference.points[0],phase:'SPACE'}),checks=[],check=(name,value)=>{assert(value,name);checks.push(name);},distance=(a,b)=>R.length(R.sub(a,b));
for(let axis=0;axis<12;axis++)for(const sign of [-1,1]){
 const s=O.create(source,{event:{spinVersion:2,flip:sign*180,twist:0,turnIn:0,turnOut:0,turnAxis:axis},settings,names,parents,reference});
 const a=s.sample(3),b=s.sample(3+1e-5),omega=R.mul(R.qlog(R.qm(b.pose.q[1],R.qinv(a.pose.q[1]))),1e5);
 check(axis+'/'+sign+' continues beyond old duration',Math.abs(s.state(3).flip-sign*540)<1e-7);
 check(axis+'/'+sign+' angular velocity follows target',distance(omega,R.mul(C.flipAxis(axis),sign*Math.PI))<1e-6);
 check(axis+'/'+sign+' rotates exactly around COM',distance(M.center(a.pose,rig),M.center(reference,rig))<1e-12);
 check(axis+'/'+sign+' preserves bone lengths',parents.every((p,i)=>p<1||Math.abs(distance(a.pose.points[i],a.pose.points[p])-distance(reference.points[i],reference.points[p]))<1e-12));
}
const tuck=R.localize(reference.points,reference.q,parents),constraints=require('./joint-rig.js').create(names,parents,reference);
for(const hinge of constraints.joints.filter(c=>c.hinge)){tuck.q[hinge.i]=R.qm(R.qexp(R.mul(hinge.axisLocal,1.7)),hinge.bind);tuck.q[hinge.parent]=R.qm(tuck.q[hinge.parent],R.qexp(R.mul(hinge.axisLocal,-1.3)));}
const tucked=require('./target-rig.js').create(names,parents,reference).project(R.fk(tuck,parents)),inertia=M.moment(M.tensor(tucked,rig),[-1,0,0]);
const s=O.create(()=>({pose:tucked,root:tucked.points[0]}),{event:{spinVersion:2,flip:180,twist:0,turnIn:0,turnOut:0},settings:{...settings,spinInertia:1},names,parents,reference});
check('Tucked pose has lower flip inertia',inertia<M.moment(M.tensor(reference,rig),[-1,0,0]));
check('Tucking increases speed by the inertia ratio',Math.abs(s.state(.5).flipRate/180-M.moment(M.tensor(reference,rig),[-1,0,0])/inertia)<1e-8);
const before=s.sample(.25),after=s.sample(.75);check('Reverse seek is deterministic',JSON.stringify(before)===JSON.stringify(s.sample(.25))&&JSON.stringify(after)===JSON.stringify(s.sample(.75)));
const events=[{id:'a',time:0,jumpPercent:0,spinVersion:2,flip:120,twist:0,turnIn:0,turnOut:0},{id:'b',time:1,jumpPercent:0,spinVersion:2},{id:'stop',time:2,jumpPercent:0,spinVersion:2,flip:0,twist:0,turnIn:.2,turnOut:.2}];
const gym=G.sequence({names,poses:[reference]},jumps,{...settings,mode:'spaceGym'},parents,events,null,reference),a=gym.sample(1-1e-6),b=gym.sample(1+1e-6),stopped=gym.sample(3);
check('New marker keeps the angular command',gym.sample(1.5).spin.target.flip===120);
check('Marker preserves orientation continuously',distance(a.pose.points[names.indexOf('head')],b.pose.points[names.indexOf('head')])<1e-5);
check('Explicit zero eases to rest and stays there',stopped.spin.target.flip===0&&distance(R.qlog(R.qm(stopped.pose.q[1],R.qinv(gym.sample(4).pose.q[1]))),[0,0,0])<1e-10);
check('Stop does not reset orientation',distance(R.qlog(R.qm(stopped.pose.q[1],R.qinv(reference.q[1]))),[0,0,0])>1);
check('Legacy angle migrates once to reference speed',C.sanitizeJump({flip:90,turnDuration:.8}).flip===112.5&&C.sanitizeJump(C.sanitizeJump({flip:90,turnDuration:.8})).flip===112.5);
check('Blank keeps command and zero remains explicit',C.sanitizeJump({spinVersion:2}).flip===null&&C.sanitizeJump({spinVersion:2,flip:0}).flip===0);

// A marker encountered during a ramp keeps the ongoing command curve.
const rampEvents=[{id:'ramp',time:0,jumpPercent:0,spinVersion:2,flip:240,twist:-60,turnIn:1,turnOut:.2},{id:'keep',time:.25,jumpPercent:0,spinVersion:2}];
const rampGym=G.sequence({names,poses:[reference]},jumps,{...settings,mode:'spaceGym'},parents,rampEvents,null,reference),single=G.sequence({names,poses:[reference]},jumps,{...settings,mode:'spaceGym'},parents,rampEvents.slice(0,1),null,reference);
for(const t of [.25,.4,.8,1,2]){check('Keep preserves ramp at '+t,Math.abs(rampGym.sample(t).spin.target.flip-single.sample(t).spin.target.flip)<1e-10);check('Keep preserves orientation at '+t,distance(R.qlog(R.qm(rampGym.sample(t).pose.q[1],R.qinv(single.sample(t).pose.q[1]))),[0,0,0])<.0003);}
for(const [flip,twist] of [[0,180],[0,-180],[180,240],[-360,-120],[720,360]]){
 const motion=O.create(source,{event:{spinVersion:2,flip,twist,turnIn:.2,turnOut:.1},settings,names,parents,reference});for(const t of [.1,.5,2,5]){const p=motion.sample(t);check('Mixed axes COM '+flip+'/'+twist+'/'+t,distance(M.center(p.pose,rig),M.center(reference,rig))<1e-12);check('Unit rotation '+flip+'/'+twist+'/'+t,Math.abs(R.length(p.pose.q[1])-1)<1e-10);}
}
const delayed=O.create(source,{event:{spinVersion:2,flip:90,turnDelay:.3,turnIn:.2},settings,names,parents,reference});check('Delay holds initial orientation',distance(delayed.sample(.3).pose.points[7],reference.points[7])<1e-10);check('Delay then ramps into persistent spin',delayed.sample(2).spin.flip>120);
const pending=[{id:'one',time:0,jumpPercent:0,spinVersion:2,flip:240,twist:0,turnIn:1},{id:'later',time:.1,jumpPercent:0,spinVersion:2,flip:360,turnDelay:2},{id:'override',time:.2,jumpPercent:0,spinVersion:2,flip:60,turnIn:.4,turnOut:.4}];
const chain=G.sequence({names,poses:[reference]},jumps,{...settings,mode:'spaceGym'},parents,pending,null,reference),original=G.sequence({names,poses:[reference]},jumps,{...settings,mode:'spaceGym'},parents,pending.slice(0,1),null,reference);
check('A new command interrupts a pending delayed command at the live ramp value',Math.abs(chain.sample(.2).spin.target.flip-original.sample(.2).spin.target.flip)<1e-9);
for(const gain of [0,.5,1]){const motion=O.create(()=>({pose:tucked,root:tucked.points[0]}),{event:{spinVersion:2,flip:180,turnIn:0,turnOut:0},settings:{...settings,spinInertia:gain},names,parents,reference});check('Inertia control interpolates multiplier '+gain,Math.abs(motion.sample(.5).spin.flipScale-(1+gain*(s.state(.5).flipScale-1)))<1e-8);}
console.log(JSON.stringify({passed:true,checks:checks.length,tuckMultiplier:s.state(.5).flipScale},null,2));
