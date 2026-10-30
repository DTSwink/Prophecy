// A feasible leading-foot/hand fixture with actual body contacts; no imaginary capsule support.
// Hand marker is at 1.95 s with current strength tiers; production scene is untouched.
// Offline mass-centre conservation checks. No Jolt world, policy worker or UI.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),N=require('./hand-inertia.js'),F=require('./flight.js');
const read=file=>JSON.parse(fs.readFileSync(new URL(file,import.meta.url))),manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest);
const {add,sub,mul,length,rotate,qm}=R,dist=(a,b)=>length(sub(a,b)),com=p=>S.com(p,names,parents,reference),checks=[];
function check(label,condition){assert(condition,label);checks.push(label);}
const release=.7,initialCOM=com(reference),translation=t=>[2*t,3*t+.5*t*t,-t+.2*t*t];
const argumentCalls=[];
function source(t,angleScale=1){
 argumentCalls.push([t,angleScale]);
 const angle=t<=release?0:angleScale*.8*Math.sin(19*(t-release)),q=R.qexp([angle,.2*angle,-.3*angle]),pelvis=reference.points[1];
 const pose={points:reference.points.map(p=>add(add(pelvis,rotate(q,sub(p,pelvis))),translation(t))),q:reference.q.map(v=>qm(q,v))};pose.axes=pose.q.map(R.toAxes);
 return {pose,root:pose.points[0],vy:3+t,phase:t<=release?'PUSH':'RISE',supportState:t<=release?'PIN':'BLEND'};
}
const wrapper=N.create(source,{release,cap:8,names,parents,reference}),expectedOrigin=add(initialCOM,translation(release)),expectedVelocity=[2,3+release,-1+.4*release];
check('Release mass centre uses real collider masses and centres',dist(wrapper.diagnostics.position,expectedOrigin)<1e-12);
check('One-sided second-order derivative retains incoming velocity',dist(wrapper.diagnostics.velocity,expectedVelocity)<1e-9);
for(const t of [-.01,0,release-.00001,release]){
 const cached=source(t),constant=N.create(()=>cached,{release,cap:8,names,parents,reference});
 check('Contact frame stays identical at '+t,constant.sample(t)===cached);
}
let largestOriginalError=0,largestCorrectedError=0;
for(let i=1;i<=90;i++){
 const t=release+i/120,age=t-release,raw=source(t),frame=wrapper.sample(t),expected=add(expectedOrigin,add(mul(expectedVelocity,age),[0,-4.905*age*age,0]));
 const error=dist(com(frame.pose),expected);largestCorrectedError=Math.max(largestCorrectedError,error);largestOriginalError=Math.max(largestOriginalError,dist(com(raw.pose),expected));
 check('Mass centre follows gravity at sample '+i,error<1e-9);
 check('Articulation is unchanged at sample '+i,frame.pose.q.every((q,j)=>q.every((v,k)=>v===raw.pose.q[j][k])));
 const correction=sub(frame.root,raw.root);
 check('All points and reported root share one translation at sample '+i,frame.pose.points.every((p,j)=>dist(sub(p,raw.pose.points[j]),correction)<1e-12));
}
check('Fixture actually exposes a non-ballistic source',largestOriginalError>.5);
const expected=JSON.stringify(wrapper.sample(1.13));wrapper.sample(10);wrapper.sample(-1);check('Arbitrary seeking has no accumulated state',JSON.stringify(wrapper.sample(1.13))===expected);
const angled=wrapper.sample(1.1,2);check('Legacy flip arguments reach source',argumentCalls.at(-1)[1]===2);
check('Alternate pose overlays retain ballistic COM',dist(com(angled.pose),wrapper.trajectory(1.1).position)<1e-11);
check('The selected overlay orientation is preserved',JSON.stringify(angled.pose.q)===JSON.stringify(source(1.1,2).pose.q));
const capAt=wrapper.diagnostics.capTime,h=1e-5,vc=mul(sub(wrapper.trajectory(capAt+h).position,wrapper.trajectory(capAt-h).position),1/(2*h));
check('Downward speed approaches its cap without a position or velocity jump',Math.abs(vc[1]+8)<.00003);
check('Fall speed stays capped',wrapper.trajectory(capAt+10).velocity[1]===-8);
check('Fall cap does not change horizontal momentum',dist(wrapper.trajectory(capAt+10).velocity,[2,-8,-.72])<1e-9);
const fastSource=t=>{const delta=[0,-30*t,0],pose={...reference,points:reference.points.map(p=>add(p,delta))};return {pose,root:pose.points[0]};};
const fast=N.create(fastSource,{release:0,cap:10,names,parents,reference});
check('Already excessive fall speed is not impulsively reset on release',Math.abs(fast.trajectory(.1).velocity[1]+30)<1e-8);
check('Excessive inherited fall speed does not keep accelerating',Math.abs(fast.trajectory(1).velocity[1]+30)<1e-8);
for(const overrides of [{release:Infinity},{release:NaN},{names:[]},{reference:{}}]){
 const disabled=N.create(source,{release,cap:8,names,parents,reference,...overrides});
 check('Invalid seed disables correction '+JSON.stringify(overrides),!disabled.diagnostics.enabled&&disabled.trajectory(1)===null);
}
const bad={pose:{points:[],q:[]},root:[0,0,0]},broken=N.create(()=>bad,{release,names,parents,reference});
check('Invalid source pose is passed through without invented coordinates',!broken.diagnostics.enabled&&broken.sample(1)===bad);
const liveBad=N.create(t=>t>release+.1?bad:source(t),{release,names,parents,reference});
check('A bad later frame cannot contaminate the deterministic trajectory',liveBad.sample(1)===bad&&Number.isFinite(liveBad.trajectory(1).position[1]));

// The user's saved 90-degree flip -> left hand at 50% launch, reconstructed
// from its frozen phase-bank slot. This does not read or mutate live settings.
function bank(){
 const meta=read('data/walk-drawn-phases.json'),count=Math.ceil(5*meta.fps)+2,width=3+meta.names.length*12,bytes=Buffer.alloc(count*width*4),fd=fs.openSync(new URL('data/walk-drawn-phases.bin',import.meta.url),'r');
 try{assert.equal(fs.readSync(fd,bytes,0,bytes.length,0),bytes.length);}finally{fs.closeSync(fd);}
 const roots=[],poses=[];for(let f=0;f<count;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}
 return F.decodeNN({...meta,duration:5,roots,poses});
}
const run=bank(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(f=>read(f).clips).map(F.decodeJump),settings=C.sanitize({jumpFoot:'L',loadYMs:200,loadFullMs:300,mode:'walk',motion:'kinematic',runSeconds:1,runPhase:0,jumpEarly:.1,jumpBlend:.4,legBlend:.2,handBend:.35,loadMs:100,rebound:.5,supportCone:30,supportReach:.99,supportTrigger:.05,supportAlpha:1,supportSpeed:800,jumpSkew:.5,matchLeg:true,surfaceIK:true,trimLoop:true,trimOut:2.55,airFlip:false,flipAngle:0,twistAngle:0,ramps:false,attack:'slashLD',jumpEvents:[{id:'first',time:56/60,surface:'floor',pushWith:'foot',flip:90},{id:'hand',time:1.95,surface:'auto',pushWith:'handL',jumpPercent:50}],platforms:[{id:'floor',position:[0,-.2,-.5599910537770252],size:[3.6,.4,66.20677485127891],rotation:[0,0,0,1]}]});
const sequence=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:2.55}),segment=sequence.segments[1],inertia=segment.inertia;
check('Saved hand push really releases',sequence.events[1].status==='Push'&&inertia?.diagnostics.enabled);
check('No capsule landing disturbs the audited free flight',sequence.landings.length===0);
let approachCOMError=0,approachGravityError=0;
for(let i=0;i<=12;i++){
 const age=.02+i/240,t=segment.supportStart+age,h=1/240,frame=sequence.sample(t),wanted=segment.support.inertia.comAt(age);
 approachCOMError=Math.max(approachCOMError,dist(com(frame.pose),wanted));
 const acceleration=mul(add(sub(com(sequence.sample(t+h).pose),mul(com(frame.pose),2)),com(sequence.sample(t-h).pose)),1/(h*h));
 approachGravityError=Math.max(approachGravityError,dist(acceleration,[0,-9.81,0]));
}
check('Airborne hand approach conserves mass centre before capsule contact',approachCOMError<3e-9);
check('Airborne torso fold adds no COM acceleration before contact',approachGravityError<.0002);
const pairSettings={...settings,jumpEvents:settings.jumpEvents.map((e,i)=>i?{...e,pushWith:'handBoth'}:e)},pairSequence=F.sequence(run,jumps,pairSettings,parents,reference,null,null,{horizon:2.55}),pairSegment=pairSequence.segments[1];
check('Two-hand COM fixture retains both feasible contacts',pairSegment.support.paired);
let pairApproachError=0;
for(let i=0;i<=12;i++){const age=.02+i/240;pairApproachError=Math.max(pairApproachError,dist(com(pairSequence.sample(pairSegment.supportStart+age).pose),pairSegment.support.inertia.comAt(age)));}
check('Both approaching hands share one conserved full-body COM',pairApproachError<3e-9);
let rawError=0,visibleError=0,gravityError=0;
for(let i=Math.ceil((segment.airStart+.01)*60);i<=Math.floor(settings.trimOut*60);i++){
 const t=i/60,wanted=inertia.trajectory(t),frame=sequence.sample(t),raw=segment.rawSample(t);
 rawError=Math.max(rawError,dist(com(raw.pose),wanted.position));visibleError=Math.max(visibleError,dist(com(frame.pose),wanted.position));
 const a=mul(add(sub(com(sequence.sample(t+1/60).pose),mul(com(frame.pose),2)),com(sequence.sample(t-1/60).pose)),3600);
 if(t-1/60>segment.airStart)gravityError=Math.max(gravityError,dist(a,[0,-9.81,0]));
}
check('Final raw source conserves COM through release blending',rawError<1e-10);
check('Visible 60Hz playback conserves COM before any collision',visibleError<1e-8);
check('Visible free-flight COM accelerates only under gravity',gravityError<1e-6);
const preRelease=segment.spin.sample(segment.airStart),post=segment.rawSample(segment.airStart);
check('Correction leaves the pinned release pose unchanged',preRelease.pose.points.every((p,i)=>dist(p,post.pose.points[i])<1e-10));
// Check final composition, not only the standalone F.create path.
const turning={...settings,jumpEvents:settings.jumpEvents.map((e,i)=>i?{...e,flip:180,twist:120,turnDuration:.25}:e)},turnSeq=F.sequence(run,jumps,turning,parents,reference,null,null,{horizon:2.55}),turnSeg=turnSeq.segments[1];
let overlayError=0;for(let i=Math.ceil((turnSeg.airStart+.01)*60);i<=153;i++){const t=i/60;overlayError=Math.max(overlayError,dist(com(turnSeg.rawSample(t).pose),turnSeg.inertia.trajectory(t).position));}
check('Final flip/twist overlays are inside COM correction',overlayError<1e-10);
const attackMetadata=read('data/vanilla.json'),attackErrors={};
for(const attack of ['slashR','KickL','headbutt']){
 const meta=attackMetadata.clips.find(c=>c.name===attack),bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),buffer=bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),clip=C.decode(meta,buffer,names,parents);
 const tune={...turning,kickToArmed:true,jumpEvents:turning.jumpEvents.map((e,i)=>i?{...e,attack,attackIn:.1}:e)},seq=F.sequence(run,jumps,tune,parents,reference,null,new Map([[attack,clip]]),{horizon:2.55}),seg=seq.segments[1];
 check(attack+' actually creates an attack overlay',!!seg.attack);
 let error=0;for(let i=Math.ceil((seg.airStart+.01)*60);i<=153;i++){const t=i/60;error=Math.max(error,dist(com(seg.rawSample(t).pose),seg.inertia.trajectory(t).position));}
 attackErrors[attack]=error;check(attack+' final animation/compensation overlay conserves COM',error<1e-10);
}
const direct=F.create(run,jumps,{...settings,loadMs:0,loadYMs:0,loadFullMs:0},parents,reference,{time:.1,hand:'handL',surface:S.ground(20)});
check('Zero-load direct hand pushes have a finite conserved COM',Number.isFinite(direct.airStart)&&direct.inertia?.diagnostics.enabled&&dist(com(direct.sample(direct.airStart+.15).pose),direct.inertia.trajectory(direct.airStart+.15).position)<1e-10);
console.log(JSON.stringify({checks:checks.length,synthetic:{largestOriginalError,largestCorrectedError},saved:{release:segment.airStart,seed:inertia.diagnostics,approachCOMError,approachGravityError,rawError,visibleError,gravityError},pairApproachError,overlayError,attackErrors,zeroLoadRelease:direct.airStart},null,2));
