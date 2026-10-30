// Frozen local motions only: no live NN, UI or saved-state writes.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js'),F=require('./flight.js'),I=require('./idle.js'),S=require('./support.js'),B=require('./bounce.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),bytes=fs.readFileSync(new URL('data/idle.bin',import.meta.url)),idle=I.create(read('data/idle.json'),bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),manifest);
const check=(ok,label)=>assert(ok,label),settings=C.sanitize({mode:'idle',motion:'kinematic',ramps:false,surfaceIK:false,supportAlpha:0}),floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,20],.4);
for(const [percent,tier,ms] of [[1,'X',100],[35,'X',100],[35.01,'Y',200],[70,'Y',200],[70.01,'100',300],[100,'100',300],[400,'100',300]]){const b=C.jumpBuild(settings,percent);check(b.tier===tier&&b.ms===ms,'threshold '+percent);}
const ordered=C.sanitize({jumpBuildX:90,jumpBuildY:20,loadMs:200,loadYMs:100,loadFullMs:50});check(ordered.jumpBuildX<ordered.jumpBuildY&&ordered.loadYMs>=ordered.loadMs&&ordered.loadFullMs>=ordered.loadYMs,'ordered thresholds/times');
check(C.jumpBuild(C.sanitize({loadMs:140}),100).ms===420,'old tuned load scales default larger times');
const reports=[];
for(const hand of ['foot','handBoth'])for(const percent of [25,50,100]){
 const input={...settings,platforms:[S.platformRecord(floor)],jumpEvents:[{id:'j',time:.1,pushWith:hand,jumpPercent:percent}]};
 const sequence=F.sequence(idle.motion(),jumps,input,parents,reference,null,null,{horizon:1.5}),segment=sequence.segments[0],b=segment.bounce;
 check(b&&Number.isFinite(segment.airStart),'finite '+hand+percent);check(b.didPush,'push '+hand+percent);
 if(hand==='handBoth')check(segment.support.paired,'both palms used');
 if(percent>35)check(b.loadDuration<=segment.build.ms/1000+1/480,'buildup respects requested time and available reach');
 let minHip=Infinity,maxHip=-Infinity,pin=0,reachError=0;
 for(let i=0;i<=Math.ceil(b.releaseTime*240);i++){
  const t=segment.contactTime+Math.min(b.releaseTime,i/240),frame=sequence.sample(t),p=frame.pose;
  check(p.points.flat().every(Number.isFinite),'finite pose');if(!frame.capsule?.poseContact)check(frame.root[1]>=-1e-7,'standing capsule stays above floor');
  const h=p.points[names.indexOf('pelvis')][1];minHip=Math.min(minHip,h);maxHip=Math.max(maxHip,h);
  if(frame.supportState==='PIN'){
   const c=segment.contactMotion.sample(t-segment.contactTime,frame.root),contacts=c.hands||[{...c,leg:segment.support.leg}];
   for(const a of contacts){pin=Math.max(pin,R.length(R.sub(p.points[a.leg.foot],a.foot)));reachError=Math.max(reachError,R.length(R.sub(p.points[a.leg.hip],p.points[a.leg.foot]))-a.leg.reach*.99);}
  }
 }
 if(percent>35||hand!=='foot')check(pin<1e-5,'pin '+hand+percent);check(reachError<1e-5,'reach '+hand+percent);
 const t=segment.contactTime+b.loadDuration*.5,pose=JSON.stringify(sequence.sample(t));sequence.sample(segment.airStart+.2);check(JSON.stringify(sequence.sample(t))===pose,'seek stable');
 reports.push({hand,percent,tier:segment.build.tier,load:b.loadDuration,release:b.releaseTime,pelvisTravel:maxHip-minHip,pin,reachError});
 for(const age of [.03,.1,.2]){const frame=sequence.sample(segment.airStart+age);if(frame.handInertia)check(R.length(R.sub(S.com(frame.pose,names,parents,reference),frame.handInertia.com))<1e-8,'hand COM after extended load');}
 if(percent>35||hand!=='foot')for(const t of [segment.jumpStart,segment.airStart]){const a=sequence.sample(t-1e-7).pose,b=sequence.sample(t+1e-7).pose;check(Math.max(...a.points.map((p,i)=>R.length(R.sub(p,b.points[i]))))<(hand==='foot'?1e-3:1e-4),'continuous load/push/release '+hand+percent+' '+t);}
}
for(const normal of [[0,1,0],[Math.SQRT1_2,Math.SQRT1_2,0],[1,0,0]])for(const buildMs of [200,300]){
 const b=B.create({root:normal,hip:normal,foot:[0,0,0],normal,direction:R.unit(R.add(normal,[0,1,0])),incoming:R.mul(normal,-1),reach:1.2,maxReach:1.188,loadMs:100,buildMs,rebound:.5,launchSpeed:4.5,cap:20,rolling:()=>({foot:[0,0,0],valid:true}),carry:F.carryVelocity});
 check(b.didPush&&b.loadDuration<=buildMs/1000+1/480,'inclined buildup push');
 for(let t=0;t<=b.releaseTime;t+=1/1920){const f=b.sample(t);check(f.p.every(Number.isFinite)&&R.length(f.p)<=1.188+1e-7&&R.length(f.p)>=.7-1e-7&&R.dot(f.p,normal)>=.144-1e-7,'inclined clearance/reach');}
}
// Space markers stay contact-free, including 0% actions.
const space=F.sequence(idle.motion(),jumps,{...settings,mode:'spaceGym',jumpEvents:[{id:'space',time:.1,jumpPercent:0,pushWith:'handBoth'}]},parents,reference,null,null,{horizon:.5});check(space.sample(.4).pose.points.flat().every(Number.isFinite),'zero gravity action');
const requests=[],policy=async request=>{
 requests.push(request);const pose=request.seeds[1],origin=request.roots[1];
 return {names:request.names.slice(1),fps:30,duration:(request.frames-1)/30,roots:request.roots.slice(1,request.frames+1),poses:Array.from({length:request.frames},(_,i)=>({points:pose.points.slice(1).map(p=>R.add(p,R.sub(request.roots[i+1],origin))),axes:pose.axes.slice(1)})),continuation:{ticks:(request.continuation?.ticks||0)+request.frames-1}};
};
const input={...settings,platforms:[S.platformRecord(floor)],trimOut:.2,jumpEvents:[{id:'j',time:.1,pushWith:'foot',jumpPercent:100}]};
const partial=await F.prepare(idle.motion(),jumps,input,parents,reference,policy),prefix=JSON.stringify(partial.sample(.2));
check(partial.preparedThrough===.2,'new buildup preparation stops at trim');await partial.extend(1.5);
check(JSON.stringify(partial.sample(.2))===prefix,'new buildup extension preserves prefix');
const whole=await F.prepare(idle.motion(),jumps,{...input,trimOut:1.5},parents,reference,policy);
for(const t of [.2,.3,.4,.6,.9,1.5]){const a=partial.sample(t).pose,b=whole.sample(t).pose;check(Math.max(...a.points.map((p,i)=>R.length(R.sub(p,b.points[i]))))<1e-8,'new buildup incremental/full equivalence');}
const customized=C.sanitize({...settings,jumpBuildX:40,jumpBuildY:80,loadYMs:350,loadFullMs:600,buildDepth:.12});check(JSON.stringify(C.sanitize(JSON.parse(JSON.stringify(customized))))===JSON.stringify(customized),'tier options survive save/reload');
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8'),panel=html.slice(html.indexOf('id="minorOptions"'),html.indexOf('<div class="readouts">'));
for(const id of ['jumpBuildX','jumpBuildY','loadYMs','loadFullMs','buildDepth'])check(panel.indexOf('id="'+id+'"')>panel.indexOf('id="handBend"')&&html.split('id="'+id+'"').length===2,'option appended once at bottom: '+id);
console.log(JSON.stringify({passed:true,reports},null,2));
