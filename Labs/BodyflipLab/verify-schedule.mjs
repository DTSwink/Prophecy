import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),m=read('data/manifest.json');
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),checks=[],measurements=[];
const check=(n,v)=>{assert(v,n);checks.push(n);},dist=(a,b)=>R.length(R.sub(a,b));
const settings=C.sanitize({jumpSkew:0,runPhase:.61,supportCone:60,supportAlpha:6,supportSpeed:500,footRollSpeed:400});
const run=F.decodeNN(await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:.61,drawn:true})})).json());
const event=(time,surface='auto',id='m'+time)=>({id,time,surface});
const make=(events,extra={})=>F.sequence(run,jumps,{...settings,jumpEvents:events,...extra},m.parents);
check('Legacy timing migrates to one marker',F.eventsFor(settings)[0].time===.9);
const clean=C.sanitize({...settings,jumpEvents:[event(1.234),event(.4)]});
check('Markers sort and snap to 60 Hz',clean.jumpEvents[0].time===.4&&clean.jumpEvents[1].time===74/60);
check('Marker identities survive sorting and sanitation',JSON.stringify(C.sanitize(clean).jumpEvents)===JSON.stringify(clean.jumpEvents));
for(const surface of S.terrain(4.88)){
 check(surface.id+' unit normal',Math.abs(R.length(surface.normal)-1)<1e-10);
 if(surface.id!=='floor')check(surface.id+' is 45 degrees',Math.abs(surface.normal[1]-Math.SQRT1_2)<1e-10);
 const [a,b,c,d]=surface.bounds;
 for(const p of [[a,0,c],[b,0,d],[(a+b)/2,0,(c+d)/2]])check(surface.id+' query and render plane agree '+p,dist(surface.closest(surface.world(p)),surface.world(p))<1e-9);
 const flat={normal:[0,1,0],bounds:surface.bounds,project:p=>[p[0],0,p[2]],closest:p=>[Math.max(a,Math.min(b,p[0])),0,Math.max(c,Math.min(d,p[2]))]};
 for(const angle of [0,30,60]){
  const apex=[a+.2,.4,c+.2],wanted=[b+1,0,d+1],local=S.coneTarget(apex,wanted,flat,angle),world=S.coneTarget(surface.world(apex),surface.world(wanted),surface,angle);
  check(surface.id+' rotated cone validity '+angle,local.valid===world.valid);
  if(local.valid)check(surface.id+' rotated closest cone point '+angle,dist(surface.world(local.contact),world.contact)<1e-8);
 }
 check(surface.id+' deep back face rejected',!S.coneTarget(surface.world([(a+b)/2,-.1,(c+d)/2]),surface.world([(a+b)/2,0,(c+d)/2]),surface,30).valid);
}
const first=make([event(.9,'floor')]);
check('First floor push succeeds',first.events[0].status==='Push');
for(const side of ['left','right','auto']){
 const start=performance.now(),sequence=make([event(.9,'floor'),event(1.8,side)]),elapsed=performance.now()-start,segment=sequence.segments[1],surface=segment.surface,l=segment.support.leg;
 check(side+' second push succeeds',sequence.events[1].status==='Push');
 check(side+' waits for contact after marker',segment.jumpStart>=1.8);
 for(const u of [0,.25,.5,.75,1]){
  const t=segment.jumpStart+segment.release*u,frame=sequence.sample(t),sole=R.add(frame.pose.points[l.foot],S.lowestOffset(frame.pose,l,surface.normal));
  check(side+' sole on ramp throughout push '+u,dist(surface.closest(sole),sole)<3e-5);
  check(side+' marker lies on ramp '+u,dist(surface.closest(frame.supportTarget),frame.supportTarget)<2e-5);
  check(side+' leg obeys reach '+u,dist(frame.pose.points[l.hip],frame.pose.points[l.foot])<=segment.support.maxReach+1e-6);
 }
 for(const t of [.1,.9,1,1.5,1.799])check(side+' earlier motion preserved '+t,JSON.stringify(sequence.sample(t).pose)===JSON.stringify(first.sample(t).pose));
 const a=sequence.sample(segment.jumpStart-1e-7),b=sequence.sample(segment.jumpStart+1e-7);
 check(side+' root continuous at push',dist(a.root,b.root)<1e-5);
 check(side+' pelvis continuous at push',dist(a.pose.points[1],b.pose.points[1])<1e-5);
 const signature=JSON.stringify(sequence.sample(2.1));sequence.sample(4);sequence.sample(.2);
 check(side+' seek deterministic',signature===JSON.stringify(sequence.sample(2.1)));
 check(side+' push leaves surface along its normal',R.dot(R.sub(sequence.sample(segment.jumpStart+.02).root,sequence.sample(segment.jumpStart).root),surface.normal)>0);
 measurements.push({side,planMilliseconds:elapsed,events:sequence.events,release:segment.release});
}
const miss=make([event(.9,'floor'),event(1.1)]),bad=miss.segments[1];
check('Too early ramp attempt misses',miss.events[1].status==='Miss');
for(const t of [bad.abortTime,.5+bad.abortTime,3]){
 check('Miss preserves incoming root '+t,dist(miss.sample(t).root,first.sample(t).root)<1e-9);
 check('Miss preserves incoming pelvis '+t,dist(miss.sample(t).pose.points[1],first.sample(t).pose.points[1])<1e-9);
}
const overlap=make([event(.9,'floor'),event(.95)]);
const triple=make([event(.9,'floor'),event(1.8),event(2)]);
check('Three scheduled jumps can succeed',triple.events.every(e=>e.status==='Push'));
check('Auto can alternate ramps',triple.events[1].surfaceId==='right'&&triple.events[2].surfaceId==='left');
check('Third flight remains finite',triple.sample(4).pose.points.flat().every(Number.isFinite));
check('Overlapping support is reported busy',overlap.events[1].status==='Busy');
check('Busy marker does not restart push',JSON.stringify(overlap.sample(1.5).pose)===JSON.stringify(first.sample(1.5).pose));
const empty=make([]);check('Deleting every marker removes all jumps',empty.segments.length===0&&empty.events.length===0);
check('Unscheduled fall caps speed',Math.abs(empty.sample(10).vy+settings.fallCap)<1e-10);
check('Unscheduled pelvis cannot rebound',empty.sample(2).pose.points[1][1]<empty.sample(1.5).pose.points[1][1]);
const disabled=make([event(1.8,'left')],{ramps:false});check('Disabled surface cannot launch',disabled.events[0].status==='Miss'&&disabled.segments.length===0);
// One small Jolt instance verifies the same slabs can be recreated and retired.
globalThis.Recovery=R;const {createPhysics}=await import('./physics.mjs'),physics=await createPhysics(m,run.poses[0]);
for(const ramps of [true,false,true]){physics.configure({dynamic:true,kinematic:true,surfaces:S.terrain(first.edge,ramps)});physics.reset(first.sample(.9).pose);check('Jolt terrain reconfigure '+ramps,physics.diagnostics().finite);}
physics.dispose();
fs.writeFileSync(new URL('schedule-verification.json',import.meta.url),JSON.stringify({passed:true,checks,measurements},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
