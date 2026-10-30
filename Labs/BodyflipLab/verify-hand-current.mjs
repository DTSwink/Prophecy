// Historical contact/COM fixtures use equal tier times to retain their original loading.
// Offline regression for the saved 180-degree flip -> left-hand floor push.
// Read the exact phase-bank rollout; no Saved files, HTTP, browser or NN worker.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js'),T=require('./torso.js');
const read=name=>JSON.parse(fs.readFileSync(new URL(name,import.meta.url)));
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest);
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(name=>read(name).clips).map(F.decodeJump);
function bank(gait='walk',drawn=true,seconds=5,phase=0){
 const stem=`data/${gait}${drawn?'-drawn':''}-phases`,meta=read(stem+'.json');
 const count=Math.ceil(seconds*meta.fps)+2,width=3+meta.names.length*12;
 const bytes=Buffer.alloc(count*width*4),fd=fs.openSync(new URL(stem+'.bin',import.meta.url),'r');
 try {assert.equal(fs.readSync(fd,bytes,0,bytes.length,Math.round(phase*meta.stride)*meta.framesPerPhase*width*4),bytes.length);} finally {fs.closeSync(fd);}
 const roots=[],poses=[];
 for(let frame=0;frame<count;frame++){
  const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((frame*width+i)*4));
  roots.push(row.slice(0,3));
  poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});
 }
 return F.decodeNN({...meta,duration:seconds,roots,poses});
}
const run=bank(),settings=C.sanitize({loadYMs:100,loadFullMs:100,mode:'walk',motion:'kinematic',runSeconds:1,runPhase:0,jumpEarly:.1,
 jumpBlend:.2,legBlend:.2,handBend:.35,loadMs:100,rebound:.5,supportCone:30,supportReach:.99,
 supportTrigger:.05,supportAlpha:1,supportSpeed:800,jumpSkew:.5,matchLeg:true,surfaceIK:true,
 trimLoop:true,trimOut:2.55,airFlip:false,flipAngle:0,twistAngle:0,ramps:false,attack:'slashLD',
 jumpEvents:[{id:'first',time:56/60,surface:'floor',pushWith:'foot',flip:180},
  {id:'hand',time:1.8,surface:'auto',pushWith:'handL'}],
 platforms:[
  {id:'floor',position:[0,-.2,-.5599910537770252],size:[3.6,.4,66.20677485127891],rotation:[0,0,0,1]},
  {id:'left',position:[-2.163746750430836,2.07889393668845,10.880017892445949],size:[6,.12,18],rotation:[0,0,-.3826834323650897,.9238795325112867]},
  {id:'right',position:[2.163746750430836,2.07889393668845,10.880017892445949],size:[6,.12,18],rotation:[0,0,.3826834323650897,.9238795325112867]}
 ]});
const {add,sub,mul,dot,length,qm,qinv,qlog}=R,dist=(a,b)=>length(sub(a,b)),angle=(a,b)=>length(qlog(qm(a,qinv(b))));
const idx=name=>names.indexOf(name),checks=[],check=(label,condition)=>{assert(condition,label);checks.push(label);};
function build(tune=settings){
 const resumes=[];
 const sequence=F.sequence(run,jumps,tune,parents,reference,data=>{
  resumes.push({time:data.time,frames:data.frames});
  // Deterministic fallback is only used by deliberate miss cases. A successful
  // handover must never ask for the superseded jump's future landing pose.
  return ()=>data.seeds[1];
 },null,{horizon:tune.trimOut});
 return {sequence,resumes};
}
const torso=T.create(names,parents,reference);
function shapes(p){
 const boxes=torso.map(spec=>T.world(p,spec));
 boxes.push({name:'pelvis',center:mul(add(p.points[idx('thigh_l')],p.points[idx('thigh_r')]),.5),forward:p.axes[1][1],side:p.axes[1][2],up:p.axes[1][0],dims:[.170,.280,.130]});
 const capsules=['l','r'].flatMap(side=>[[`upperarm_${side}`,`lowerarm_${side}`,.058],[`lowerarm_${side}`,`hand_${side}`,.048],[`thigh_${side}`,`calf_${side}`,.083],[`calf_${side}`,`foot_${side}`,.062]])
  .map(([name,end,radius])=>({name,a:p.points[idx(name)],b:p.points[idx(end)],radius}));
 const neck=p.points[idx('neck_02')],head=p.points[idx('head')];
 capsules.push({name:'head',a:neck,b:add(neck,mul(p.axes[idx('head')][0],Math.max(.054,dist(head,neck)))),radius:.1});
 return {boxes,capsules};
}
function pointBoxDistance(point,box){
 const delta=sub(point,box.center),v=[dot(delta,box.forward),dot(delta,box.side),dot(delta,box.up)];
 return Math.hypot(...v.map((n,i)=>Math.max(0,Math.abs(n)-box.dims[i]/2)));
}
function capsuleBoxGap(capsule,box){
 const at=t=>pointBoxDistance(add(capsule.a,mul(sub(capsule.b,capsule.a),t)),box);
 let lo=0,hi=1;
 for(let i=0;i<24;i++){const a=lo+(hi-lo)/3,b=hi-(hi-lo)/3;if(at(a)<at(b))hi=b;else lo=a;}
 return Math.min(at(0),at(1),at((lo+hi)/2))-capsule.radius;
}
function colliderClearance(p,surfaces){
 const {boxes,capsules}=shapes(p);let terrain=Infinity,self=Infinity;
 for(const surface of surfaces){
  const record=(point,radius=0)=>{const projection=surface.project(point);if(dist(projection,surface.closest(projection))<1e-6)terrain=Math.min(terrain,dot(sub(point,surface.origin),surface.normal)-radius);};
  for(const box of boxes)for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1])record(add(box.center,add(mul(box.forward,x*box.dims[0]/2),add(mul(box.side,y*box.dims[1]/2),mul(box.up,z*box.dims[2]/2)))));
  for(const c of capsules){record(c.a,c.radius);record(c.b,c.radius);}
 }
 for(const c of capsules)for(const b of boxes){
  // Neighboring anatomical shapes intentionally overlap at their common socket.
  if(c.name==='head'&&b.name==='spine_05'||c.name.startsWith('upperarm')&&['spine_04','spine_05'].includes(b.name)||c.name.startsWith('thigh')&&b.name==='pelvis')continue;
  self=Math.min(self,capsuleBoxGap(c,b));
 }
 return {terrain,self};
}
function inspect(sequence,label,{collisions=false,index=1}={}){
 const segment=sequence.segments[index],end=settings.trimOut,pushed=sequence.events[index]?.status==='Push';
 let pinError=0,self=Infinity,terrain=Infinity,finite=true,minRoot=Infinity,maxBoneLengthError=0,samples=0;
 const original=R.localize(run.poses[0].points,run.poses[0].q,parents);
 for(let i=Math.ceil(segment.supportStart*240);i<=Math.floor(end*240);i++){
  const t=i/240,frame=sequence.sample(t),pose=frame.pose,local=R.localize(pose.points,pose.q,parents);samples++;
  finite&&=pose.points.flat().every(Number.isFinite)&&pose.q.flat().every(Number.isFinite);
  minRoot=Math.min(minRoot,frame.root[1]);
  for(let j=2;j<names.length;j++)maxBoneLengthError=Math.max(maxBoneLengthError,Math.abs(length(local.p[j])-length(original.p[j])));
  if(frame.supportState==='PIN')pinError=Math.max(pinError,dist(pose.points[segment.supportBone],segment.contactMotion.sample(t-segment.contactTime).foot));
  if(collisions){const result=colliderClearance(pose,sequence.surfaces);self=Math.min(self,result.self);terrain=Math.min(terrain,result.terrain);}
 }
 check(label+' finite body through entire trimmed interval',finite);
 check(label+' capsule stays above floor',minRoot>=-1e-5);
 check(label+' bones retain authored lengths',maxBoneLengthError<.008);
 check(label+' displayed palm remains pinned',pinError<2e-5);
 let joinError=0;
 for(const t of [segment.jumpStart,segment.airStart,segment.airStart+settings.jumpBlend,segment.airStart+settings.legBlend])if(Number.isFinite(t)&&t<end){
  const a=sequence.sample(t-1e-7).pose,b=sequence.sample(t+1e-7).pose;
  // root.q is a coordinate frame, not a physical collider orientation.
  for(let j=1;j<names.length;j++)joinError=Math.max(joinError,dist(a.points[j],b.points[j]),angle(a.q[j],b.q[j]));
 }
 check(label+' no release or blend-end pose jump',joinError<.001);
 const time=Math.min(end,Number.isFinite(segment.airStart)?segment.airStart+.13:2.2),expected=JSON.stringify(sequence.sample(time));
 sequence.sample(end);sequence.sample(0);check(label+' seeks are deterministic',JSON.stringify(sequence.sample(time))===expected);
 return {label,pushed,samples,pinError,joinError,maxBoneLengthError,self,terrain,contact:segment.contactTime,release:segment.airStart};
}
const start=performance.now(),{sequence,resumes}=build(),reports=[];
check('Exact saved case pushes from left hand',sequence.events[1].status==='Push'&&sequence.segments[1].supportFoot==='L');
check('Successful handover never requests obsolete landing NN',resumes.length===0);
const exact=inspect(sequence,'Saved 180-degree left-hand push',{collisions:true});reports.push(exact);
check('Recovery does not drive thigh through spine',exact.self>=-1e-4);
check('Visible torso/head/limb colliders stay above finite surfaces',exact.terrain>=-1e-4);
const recovered=sequence.segments[1].airStart+Math.max(settings.jumpBlend,settings.legBlend)+.02;
const actual=sequence.sample(recovered).pose,target=sequence.segments[0].rawSample(recovered).pose;
let recoveryRotationError=0;
for(let j=1;j<names.length;j++)recoveryRotationError=Math.max(recoveryRotationError,angle(actual.q[j],target.q[j]));
check('Hand release recovers the incoming motion, not a new foot-jump clip',recoveryRotationError<1e-6);
for(const flip of [0,90,180])for(const hand of ['handL','handR']){
 if(flip===180&&hand==='handL')continue;
 // This gait has the right wrist further from the floor at1.8s. Start its
 // inverted reach earlier; the unmodified late right-hand case legitimately misses.
 const tune={...settings,jumpEvents:settings.jumpEvents.map((event,i)=>i?{...event,pushWith:hand,time:flip===180?1.6:event.time}:{...event,flip})};
 const {sequence:variant}=build(tune);reports.push(inspect(variant,`${flip}-degree ${hand}`));
}
check('Both hands have feasible quarter-turn and inverted pushes',reports.filter(r=>/^(90|180)-degree/.test(r.label)).every(r=>r.pushed));
for(const hand of ['handL','handR']){
 const {sequence:walking}=build({...settings,jumpEvents:[{id:'walking',time:.1,pushWith:hand}]});
 check(`Ordinary walking ${hand} pushes`,walking.events[0].status==='Push');
 reports.push(inspect(walking,`Walking ${hand}`,{index:0}));
}
const {sequence:footOnly}=build({...settings,trimOut:1.8,jumpEvents:[settings.jumpEvents[0]]});
let footPrefixError=0;
for(let i=0;i<108;i++){
 const a=sequence.sample(i/60).pose,b=footOnly.sample(i/60).pose;
 for(let j=0;j<names.length;j++)footPrefixError=Math.max(footPrefixError,dist(a.points[j],b.points[j]),angle(a.q[j],b.q[j]));
}
check('Adding hand marker leaves completed foot-jump prefix unchanged',footPrefixError<1e-9);
console.log(JSON.stringify({checks:checks.length,elapsedMs:performance.now()-start,recoveryRotationError,footPrefixError,reports},null,2));
