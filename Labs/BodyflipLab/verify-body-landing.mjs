// Offline body geometry, swept contacts and seeded landing handoff.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),P=require('./body-contact.js'),K=require('./capsule.js'),R=require('./recovery.js'),S=require('./support.js'),T=require('./torso.js'),C=require('./core.js'),F=require('./flight.js');
const read=n=>fs.readFileSync(new URL(n,import.meta.url)),m=JSON.parse(read('data/manifest.json')),reference=C.poseFromShared(m),rig=P.create(m.names,m.parents,reference),checks=[];
const check=(label,ok)=>{assert(ok,label);checks.push(label);},dist=(a,b)=>R.length(R.sub(a,b));
const Renderer=vm.runInNewContext(read('renderer.js').toString()+';WebGLMotionRenderer;', {BodyflipSupport:S,BodyflipTorso:T,nameToIndex:new Map(m.names.map((n,i)=>[n,i])),parents:m.parents,posAt:(p,i)=>p.points[i],axisAt:(p,i,k)=>p.axes[i][k],add:R.add,sub:R.sub,mul:R.mul,cross:R.cross,dot:R.dot,norm:R.length,normalize:R.unit});
for(const angle of [0,.7,2.1]){
 const q=R.qexp([angle,angle*.3,0]),p={points:reference.points.map(v=>R.add(R.rotate(q,v),[2,3,-1])),q:reference.q.map(v=>R.qm(q,v))};p.axes=p.q.map(R.toAxes);
 const boxes=[],capsules=[],renderer=Object.create(Renderer.prototype);Object.assign(renderer,{torsoColliders:T.create(m.names,m.parents,reference),box:(mesh,s)=>boxes.push(s),capsule:(mesh,a,b,r)=>capsules.push({a,b,radius:r}),addSword(){}});renderer.addBody([],p);
 for(const shape of rig.shapes(p)){
  if(shape.radius)check('Rendered capsule matches contact '+shape.name+'/'+angle,capsules.some(s=>dist(s.a,shape.a)<1e-9&&dist(s.b,shape.b)<1e-9&&s.radius===shape.radius));
  else check('Rendered box matches contact '+shape.name+'/'+angle,boxes.some(s=>dist(s.center,shape.center)<1e-9&&dist(s.dims,R.mul(shape.half,2))<1e-9&&[s.forward,s.side,s.up||s.palmNormal].every((a,i)=>dist(a,shape.axes[i])<1e-9)));
 }
}
const floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,5],.02),axes=[[1,0,0],[0,1,0],[0,0,1]],box=(p,name='test')=>({name,center:p,axes,half:[.1,.1,.1]});
const fast=P.move([box([0,5,0]),box([.3,5,0])],[box([0,-5,0]),box([.3,-5,0])],[0,-5,0],[floor]);
check('Swept boxes cannot tunnel through thin platform',Math.abs(fast.root[1]-.1)<1e-5);
check('Multiple contacts do not multiply the correction',fast.root[1]<.10001);
const missed=P.move([box([6,5,0])],[box([6,-5,0])],[6,-5,0],[floor]);check('Finite platform gaps remain empty',missed.contacts.length===0&&missed.root[1]===-5);
const cap=(y)=>({name:'arm',a:[0,y,0],b:[.4,y,0],radius:.08}),capHit=P.move([cap(5)],[cap(-5)],[0,-5,0],[floor]);check('Swept limb cannot tunnel',Math.abs(capHit.root[1]-.08)<1e-5);
const pose=root=>({points:[root,R.add(root,[0,.9,0])],q:[[0,0,0,1],[0,0,0,1]],axes:[axes,axes]});
const body={move:(a,b,surfaces)=>P.move([box(a.points[1])],[box(b.points[1])],b.points[0],surfaces)};
const source=t=>{const root=[0,.2-2*t,0];return {root,pose:pose(root),phase:'FALL',airTime:1+t,vy:-2};};
const requests=[],track=K.track(source,{body,surfaces:[floor],speed:0,phase:'IDLE',gait:t=>pose([0,0,0]),fallPose:()=>pose([0,0,0]),resume:data=>{requests.push(data);return ()=>data.seeds[1];}});
const waiting=track.sample(.2);check('Standing capsule reaching floor does not land folded body',!waiting.returnedToLocomotion&&waiting.root[1]<0&&waiting.pose.points[1][1]>.1);
const end=track.sample(.7),landing=track.landings[0];check('Actual body contact starts locomotion',end.returnedToLocomotion&&Math.abs(landing.time-.5)<=1/240);
const before=track.sample(landing.time-1e-7),at=track.sample(landing.time);check('Restoring standing carrier does not lift visible body',dist(before.pose.points[1],at.pose.points[1])<1e-5);
check('Landing seed is exactly the contact pose',dist(requests[0].seeds[1].points[1],at.pose.points[1])<1e-10);
check('Locomotion root is restored above platform',at.root[1]>=0&&K.query(at.root,floor).gap>=-1e-6);
check('Rebased previous seed retains body motion',Math.abs(requests[0].seeds[0].points[1][1]-requests[0].seeds[1].points[1][1]-2/30)<.01);
check('Rebase does not inject a root-speed spike',Math.abs(at.velocity[1])<2.001);
const snapshot=JSON.stringify(track.sample(.2));track.sample(1);track.sample(0);check('Reverse seeking keeps airborne frame identical',JSON.stringify(track.sample(.2))===snapshot);
const k=Math.SQRT1_2,ramp=S.rectangle('ramp',[0,0,0],[k,k,0],[0,0,1],[-5,5,-5,5],.02),rampTrack=K.track(source,{body,surfaces:[ramp],speed:0,phase:'IDLE',gait:()=>pose([0,0,0]),fallPose:()=>pose([0,0,0])});
const rampEnd=rampTrack.sample(1);check('Pose contact lands on an incline',rampEnd.returnedToLocomotion&&rampTrack.landings.length===1);
check('Incline handoff preserves touching volume',Math.abs(P.query(box(rampEnd.pose.points[1]),ramp).gap)<1e-5);
const wall=S.rectangle('wall',[0,0,0],[1,0,0],[0,1,0],[-5,5,-5,5],.02),sideSource=t=>{const root=[0,0,-1+4*t];return {root,pose:pose(root),phase:'FALL',airTime:1,vy:0};},side=K.track(sideSource,{body,surfaces:[wall],speed:0,gait:()=>pose([0,0,0]),fallPose:()=>pose([0,0,0])});
check('Side collision does not count as landing',!side.sample(.8).returnedToLocomotion&&side.landings.length===0&&side.sample(.8).pose.points[1][2]<=-.0999);
// A low NN recovery must retain its articulation while keeping body volumes clear.
const recoveryBody={...body,resolve:(p,surfaces)=>P.move([box(p.points[1])],[box(p.points[1])],p.points[0],surfaces)};
const lowRecovery=K.track(source,{body:recoveryBody,surfaces:[floor],speed:0,phase:'IDLE',gait:()=>pose([0,0,0]),fallPose:()=>pose([0,0,0]),resume:data=>t=>{const p=data.seeds[1];return {...p,points:p.points.map((v,i)=>i===0?v:R.add(v,[0,-Math.min(.2,Math.max(0,t-data.time)),0]))};}});
const recovered=lowRecovery.sample(.8);
check('Low NN recovery body cannot pass through platform',P.query(box(recovered.pose.points[1]),floor).gap>=-1e-6);
check('Recovery clearance retains standing root reference',dist(recovered.root,recovered.pose.points[0])<1e-12&&Math.abs(recovered.root[1]-1e-6)<1e-8);
check('Recovery clearance preserves policy orientations',JSON.stringify(recovered.pose.q)===JSON.stringify(source(.5).pose.q));
// Frozen saved-scene reproduction, with a deterministic seeded policy stand-in.
const meta=JSON.parse(read('data/walk-drawn-phases.json')),count=Math.ceil(5*meta.fps)+2,width=3+meta.names.length*12,bytes=Buffer.alloc(count*width*4),fd=fs.openSync(new URL('data/walk-drawn-phases.bin',import.meta.url),'r');
try{assert.equal(fs.readSync(fd,bytes,0,bytes.length,0),bytes.length);}finally{fs.closeSync(fd);}
const roots=[],poses=[];for(let f=0;f<count;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}
const run=F.decodeNN({...meta,duration:5,roots,poses}),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>JSON.parse(read(n)).clips).map(F.decodeJump);
const settings=C.sanitize({mode:'walk',motion:'kinematic',ramps:false,surfaceIK:false,attack:'slashLD',jumpBlend:.4,legBlend:.2,airFlip:false,flipAngle:0,trimOut:2.55,platforms:[{id:'floor',position:[0,-.2,-.5599910537770252],rotation:[0,0,0,1],size:[3.6,.4,66.20677485127891]}],jumpEvents:[{id:'first',time:56/60,surface:'floor',flip:90,pushWith:'foot'},{id:'hand',time:136/60,pushWith:'handBoth',jumpPercent:50}]}),inputs=JSON.stringify(settings),seedRequests=[];
const policy=async request=>{seedRequests.push(request);const seed=request.seeds[1],origin=request.roots[1];return {names:request.names.slice(1),fps:30,duration:(request.frames-1)/30,roots:request.roots.slice(1,request.frames+1),poses:Array.from({length:request.frames},(_,i)=>({points:seed.points.slice(1).map(p=>R.add(p,R.sub(request.roots[i+1],origin))),axes:seed.axes.slice(1)})),continuation:{ticks:request.frames-1}};};
const sequence=await F.prepare(run,jumps,settings,m.parents,reference,policy),reported=sequence.sample(131/60),sceneLanding=sequence.landings[0],sceneAt=sequence.sample(sceneLanding.time),sceneBefore=sequence.sample(sceneLanding.time-1e-7),clearance=Math.min(...rig.shapes(reported.pose).map(s=>P.query(s,sequence.surfaces[0]).gap));
check('Reported F131 stays airborne despite root below floor',reported.root[1]<0&&!reported.capsule.grounded&&!reported.returnedToLocomotion&&clearance>.5);
check('Hand approach starts while genuinely airborne',!sequence.sample(settings.jumpEvents[1].time).capsule.grounded&&sceneLanding.time>settings.jumpEvents[1].time);
check('Actual body contact interrupts pending hand push honestly',sequence.events[1].status==='Miss'&&sequence.events[1].reason.includes('Body contact before push')&&sequence.pushDebug(sequence.segments[1].jumpStart)===null);
const visibleGap=Math.max(...sceneAt.pose.points.slice(1).map((p,i)=>dist(p,sceneBefore.pose.points[i+1])));
check('Actual rotated-body landing has no body teleport',visibleGap<1e-4);
check('Landing policy receives exact displayed body',seedRequests[0].seeds[1].points.slice(1).every((p,i)=>dist(p,sceneAt.pose.points[i+1])<1e-8));
check('Landing restores carrier without penetrating it',K.query(sceneAt.root,sequence.surfaces[0]).gap>=-1e-6);
check('Saved-scene test does not edit tuning or markers',JSON.stringify(settings)===inputs);
const early=F.sequence(run,jumps,{...settings,jumpEvents:settings.jumpEvents.map((e,i)=>i?{...e,time:1.95}:e)},m.parents,reference,null,null,{horizon:2.75}),hand=early.segments[1];
check('Paired spin loses contact honestly before a late push',early.events[1].status==='Miss'&&hand.spinReleaseTime<hand.jumpStart&&hand.spinContact.releases.every(r=>r.early)&&early.pushDebug(hand.jumpStart)===null);
// F136 report after moving the hand marker to F128: its release hand used
// to be counted as a new landing on the very next collision tick.
const released=F.sequence(run,jumps,{...settings,jumpEvents:settings.jumpEvents.map((e,i)=>i?{...e,time:128/60}:e)},m.parents,reference,null,null,{horizon:2.55}),releasedHand=released.segments[1],current=released.sample(136/60);
check('Hand push remains airborne at F136',!current.returnedToLocomotion&&!current.capsule.grounded);
check('Buildup reserves enough travel for an upward release',releasedHand.inertia.diagnostics.velocity[1]>0&&releasedHand.bounce.releaseTime>releasedHand.bounce.loadDuration);
check('Marker stays unchanged and capture precedes release',releasedHand.supportStart===128/60&&releasedHand.contactTime>=releasedHand.supportStart&&releasedHand.contactTime<releasedHand.airStart);
check('Full remaining trimmed motion stays airborne',released.landings.length===0&&Array.from({length:17},(_,i)=>released.sample((137+i)/60)).every(f=>!f.returnedToLocomotion));
let minClearance=Infinity,maxPin=0,maxReach=0;
for(let t=releasedHand.contactTime;t<2.55;t+=1/480){const f=released.sample(t);minClearance=Math.min(minClearance,...rig.shapes(f.pose).map(shape=>P.query(shape,released.surfaces[0]).gap));if(t<=releasedHand.airStart){const l=releasedHand.support.leg,c=releasedHand.contactMotion.sample(t-releasedHand.contactTime,f.root,f.pose);maxPin=Math.max(maxPin,dist(f.pose.points[l.foot],c.foot));maxReach=Math.max(maxReach,dist(f.pose.points[l.hip],f.pose.points[l.foot])-l.reach*.99);}}
check('Complete hand push preserves pin and arm reach',maxPin<1e-5&&maxReach<1e-5);
check('Complete hand sequence keeps body above floor',minClearance>-.0001);
released.prepareThrough(3.4);const realLanding=released.segments[1].carrier.landings[0];
check('Airborne path continues until a real body part lands',!!realLanding.bone&&realLanding.time>2.55);
check('Later landing is actual collider contact',Math.abs(P.query(rig.shapes(released.sample(realLanding.time).pose).find(s=>s.name===realLanding.bone),released.surfaces[0]).gap)<1e-5);
console.log(JSON.stringify({passed:true,checks:checks.length,landing:landing.time,visibleHandoffError:dist(before.pose.points[1],at.pose.points[1]),savedScene:{clearance,landing:sceneLanding.time,visibleGap,earlierHandRelease:hand.airStart},current:{release:releasedHand.airStart,pushMs:(releasedHand.bounce.releaseTime-releasedHand.bounce.loadDuration)*1000,velocity:releasedHand.inertia.diagnostics.velocity,landing:realLanding.time,minClearance,maxPin,maxReach}},null,2));
