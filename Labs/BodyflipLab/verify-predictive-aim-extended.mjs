// Broad offline aim audit: final constrained hit plus dense motion continuity.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),Aim=require('./attack-aim.js'),F=require('./flight.js'),I=require('./idle.js'),J=require('./joint-rig.js'),Mass=require('./mass.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),meta=read('data/vanilla.json'),catalog=new Map(meta.clips.map(v=>[v.name,C.decode(v,bytes(v.file),names,parents)])),Project=require('./target-rig.js').create(names,parents,reference),project=p=>Project.project(p),mass=Mass.model(names,parents,reference),joints=J.create(names,parents,reference);
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),m).motion();
const dist=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI,dirs=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1],...[1,-1].flatMap(x=>[1,-1].flatMap(y=>[1,-1].map(z=>[x,y,z])))],results=[],continuity=[],failures=[],capture=[];
const selected=process.env.AIM_NAMES?.split(',')||[...catalog.keys()],configs=[{flip:360,twist:150,axis:0,direct:true},{flip:-540,twist:-230,axis:3,direct:false},{flip:240,twist:480,axis:8,direct:true}];
for(const [ni,name] of selected.entries())for(const [ci,cfg] of configs.entries()){
 const settings=C.sanitize({mode:'spaceGym',spinLag:.6,spinInertia:1,kickToArmed:cfg.direct,aimWeight:1,jumpEvents:[{id:'a',time:.1,spinVersion:2,instantSpin:ci!==1,flip:cfg.flip,twist:cfg.twist,turnAxis:cfg.axis,turnIn:.3,jumpPercent:0,attack:name,attackDelay:.2}],trimOut:4}),seq=F.sequence(idle,jumps,settings,parents,reference,null,catalog,{horizon:4}),track=seq.segments[0].attack,clip=catalog.get(name),plan=Aim.create({clip,track,names,parents,reference,sampleHit:t=>seq.sample(t).pose,project}),raw=seq.sample(track.hitTime).pose;
 for(const [di,v] of dirs.entries()){
  const target=R.add(plan.origin,R.mul(R.unit(v),1.5)),sol=plan.solution(target),pose=project(plan.apply(raw,track.hitTime,target)),error=dist(R.unit(R.sub(plan.point(pose),Aim.center(pose,plan.rig))),R.unit(v)),dCOM=dist(Mass.center(raw,mass),Mass.center(pose,mass)),row={name,ci,cfg,di,v,error,dCOM,parameters:sol.parameters};results.push(row);if(error>1e-5||dCOM>1e-8||!pose.points.flat().every(Number.isFinite))failures.push(row);
 }
 const target=R.add(plan.origin,R.mul(R.unit(dirs[(ni*5+ci*3)%dirs.length]),1.5));let previous=null,max=0,maxRaw=0,peak=null,maxLimit=0;const end=Math.min(track.returnEnd+.05,4);
 for(let tick=Math.floor(track.start*240);tick<=Math.ceil(end*240);tick++){
  const t=tick/240,raw=seq.sample(t).pose,pose=project(plan.apply(raw,t,target)),a=R.localize(raw.points,raw.q,parents),b=R.localize(pose.points,pose.q,parents);
  if(previous)for(let i=1;i<names.length;i++){const d=angle(b.q[i],previous.b.q[i]),r=angle(a.q[i],previous.a.q[i]);if(d>max){max=d;peak={t,frame:t*60,bone:names[i],d,raw:r};}maxRaw=Math.max(maxRaw,r);}
  if(tick%8===0)maxLimit=Math.max(maxLimit,...joints.inspect(pose).map(j=>j.angularError));
  previous={a,b};
  if(ci===0&&['slashL','KickR','headbutt','sweepKick'].includes(name)&&tick%8===0)capture.push({name,ci,t,frame:t*60,phase:t<plan.ready?'Aim in':t<track.end?'Attack':'Return',pose,target,root:pose.points[0]});
 }
 const row={name,ci,maxDegreesPer240Hz:max,maxRawDegreesPer240Hz:maxRaw,peak,maxLimit,ready:plan.ready,hit:track.hitTime,deadline:plan.deadline,weightStart:plan.weight(track.start),weightReady:plan.weight(plan.ready)};continuity.push(row);
 console.log(JSON.stringify({name,ci,hitFailures:failures.filter(r=>r.name===name&&r.ci===ci).length,max,peak}));
}
const report={cases:results.length,maxError:Math.max(...results.map(r=>r.error)),maxCOM:Math.max(...results.map(r=>r.dCOM)),failures,continuity};fs.mkdirSync('Saved/BodyflipLab/PredictiveAim',{recursive:true});fs.writeFileSync('Saved/BodyflipLab/PredictiveAim/extended.json',JSON.stringify(report,null,2));fs.writeFileSync('Saved/BodyflipLab/PredictiveAim/colliders.json',JSON.stringify(capture));console.log(JSON.stringify({cases:report.cases,maxError:report.maxError,maxCOM:report.maxCOM,failures:failures.length}));
assert.equal(failures.length,0,'Every constrained future hit has the requested direction and COM');
for(const row of continuity){
 assert(row.maxLimit<1e-7,JSON.stringify({issue:'joint limit',...row}));
 // These fixed regression paths previously added 45-145 degree one-tick
 // discontinuities. Their corrected motion now stays below the existing
 // source's maximum; this is a test assertion, never a runtime speed clamp.
 assert(row.maxDegreesPer240Hz<row.maxRawDegreesPer240Hz+1e-5,JSON.stringify({issue:'new path spike',...row}));
 assert.equal(row.weightStart,0);assert.equal(row.weightReady,1);
 assert.equal(row.deadline,['KickL','KickR','jabL','jabR','pike'].includes(row.name)?'Armed':'Hit');
}
