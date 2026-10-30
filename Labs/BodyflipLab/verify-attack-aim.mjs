import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),H=require('./attack-inertia.js'),K=require('./kick-attack.js'),Aim=require('./attack-aim.js'),F=require('./flight.js'),I=require('./idle.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),meta=read('data/vanilla.json'),catalog=new Map(meta.clips.map(v=>[v.name,C.decode(v,bytes(v.file),names,parents)]));
const dist=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),directionError=(a,b)=>dist(R.unit(a),R.unit(b));
const app=fs.readFileSync(new URL('app.js',import.meta.url),'latin1'),code=app.slice(app.indexOf('function manualPose('),app.indexOf('function resetPhysics('));
let samples=0,maxDirectionError=0,maxCOMError=0,maxLocalError=0,maxManualError=0,maxNativeCalibrationError=0,maxPelvisTilt=0,maxChainStepSpread=0;const deadlines={};
for(const directArmed of [false,true])for(const [name,clip] of catalog){
 const settings={...C.defaults,attack:name,kickToArmed:directArmed,aim:true,aimWeight:1,airFlip:false},segment={sample:()=>({pose:reference}),airStart:.4,jumpStart:.4,abortTime:Infinity,event:{attack:name}},track=A.create({attack:name,attackIn:.2,attackOut:.25},segment,catalog,names,parents,settings,reference);segment.attack=track;
 const aim=Aim.create({clip,track,names,parents,reference,sampleHit:t=>track.sample(t).pose}),hit=track.sample(track.hitTime).pose;
 const f=clip.meta.phases.hit,i=Math.min(clip.poses.length-2,Math.floor(f)),source=C.blend(clip.poses[i],clip.poses[i+1],f-i,parents);
 maxNativeCalibrationError=Math.max(maxNativeCalibrationError,dist(aim.point(source),clip.meta.hitTarget));
 for(const t of [track.end,track.returnEnd-1e-6,track.returnEnd,track.returnEnd+2]){
  const held=aim.apply(reference,t,[.4,2,-1],1,false),expected=aim.apply(reference,aim.ready,[.4,2,-1],1,false);
  assert(dist(held.points[10],expected.points[10])<1e-9,'No forced rotation return, including after clip end');
 }
 assert.equal(aim.weight(track.returnEnd+2,false),1);
 assert.equal(aim.weight(track.returnEnd+2,true),0);
 deadlines[name]=aim.deadline;
 assert.equal(aim.deadline,['KickL','KickR','jabL','jabR','pike'].includes(name)?'Armed':'Hit');
 const armed=track.armedTime??track.start+track.duration;
 assert.equal(aim.weight(aim.ready),1);assert.equal(aim.weight(track.start),0);assert.equal(aim.weight(track.returnEnd),0);
 if(aim.deadline==='Hit')assert(aim.weight(armed)<1,'Circular attack still turns after Armed');
 for(const direction of [[0,0,-1],[1,.5,-1],[0,1,0],R.mul(aim.direction,-1),aim.direction]){
  const target=R.add(aim.origin,R.mul(R.unit(direction),R.length(aim.direction))),out=aim.apply(hit,track.hitTime,target,1);
  maxDirectionError=Math.max(maxDirectionError,directionError(R.sub(aim.point(out),Aim.center(out,aim.rig)),direction));
  // Articulation changes radial reach; the contract is target direction.
  const turn=aim.rotation(track.hitTime,target,.8),full=aim.correction(target);
  assert(Math.abs(R.length(R.qlog(turn.yaw))-.8*R.length(R.qlog(full.yaw)))<1e-8,'Amount scales pelvis yaw');
  for(const j of aim.chain)assert(Math.abs(R.length(R.qlog(turn.bends[j]))-.8*R.length(R.qlog(full.bends[j])))<1e-8,'Amount scales distributed bend');
  for(let t=track.start;t<=track.returnEnd+.01;t+=1/60){
   const raw=track.sample(t).pose,p=aim.apply(raw,t,target),before=R.localize(raw.points,raw.q,parents),after=R.localize(p.points,p.q,parents);
   assert(p.points.flat().every(Number.isFinite));assert.deepEqual(p.points[0],raw.points[0]);
   maxCOMError=Math.max(maxCOMError,dist(Aim.center(p,aim.rig),Aim.center(raw,aim.rig)));
   for(let j=2;j<names.length;j++)maxLocalError=Math.max(maxLocalError,dist(before.p[j],after.p[j]),aim.chain.includes(j)?0:angle(before.q[j],after.q[j]));
   const pelvis=names.indexOf('pelvis'),delta=R.qlog(R.qm(p.q[pelvis],R.qinv(raw.q[pelvis])));maxPelvisTilt=Math.max(maxPelvisTilt,Math.hypot(delta[0],delta[2]));
   const steps=aim.chain.map(j=>{const d=R.qm(p.q[j],R.qinv(raw.q[j])),par=parents[j],pd=R.qm(p.q[par],R.qinv(raw.q[par]));return angle(d,pd);});
   maxChainStepSpread=Math.max(maxChainStepSpread,Math.max(...steps)-Math.min(...steps));
   samples++;
  }
 }
 // Exercise actual app composition: timeline and manual, with no DOM or browser.
 const target=R.add(aim.origin,[.5,.3,-1]);
 const ctx=vm.createContext({R,C,BodyflipJumpAttack:A,BodyflipKickAttack:K,BodyflipAttackInertia:H,BodyflipAttackAim:Aim,clamp:(v,a,b)=>Math.max(a,Math.min(b,v)),names,parents,idle:reference,clip,settings:{...settings,target},flight:{sample:t=>track.sample(t),activeAt:()=>segment},vanillaManifest:meta,vanillaAttacks:catalog,manualResponse:null,simTime:track.hitTime,attackTime:-1,flip:0,twist:0,flightFrame:null});
 vm.runInContext(code,ctx);vm.runInContext('out=targetPose()',ctx);
 assert(dist(ctx.out.points[10],aim.apply(hit,track.hitTime,target).points[10])<1e-8,'App timeline uses the new aim');
 ctx.flight={sample:()=>({pose:reference}),activeAt:()=>null};ctx.simTime=0;ctx.attackTime=0;vm.runInContext('out=targetPose()',ctx);
 const manual=ctx.manualResponse.response;ctx.attackTime=manual.hitTime;ctx.simTime=manual.hitTime/settings.attackRate;vm.runInContext('out=targetPose()',ctx);
 const ma=Aim.create({clip,track:manual,names,parents,reference,sampleHit:t=>manual.sample(t)});
 maxManualError=Math.max(maxManualError,directionError(R.sub(ma.point(ctx.out),Aim.center(ctx.out,ma.rig)),R.sub(target,ma.origin)));
 ctx.settings.aim=false;vm.runInContext('out=targetPose()',ctx);assert(dist(ctx.out.points[10],manual.sample(manual.hitTime).points[10])<1e-8,'Aim off retains original pose');
 ctx.settings.aim=true;ctx.settings.target=R.add(ma.origin,[-1,0,-1]);vm.runInContext('out=targetPose()',ctx);
 assert(directionError(R.sub(ma.point(ctx.out),ma.origin),[-1,0,-1])<1e-8,'Moved target reuses the plan without stale aim');
 ctx.settings.undoRotation=false;ctx.attackTime=-1;ctx.simTime=manual.returnEnd+2;vm.runInContext('out=targetPose()',ctx);
 const heldManual=ma.apply(manual.sample(ctx.simTime),ctx.simTime,ctx.settings.target,1,false);
 assert(dist(ctx.out.points[10],heldManual.points[10])<1e-8,'App holds manual orientation after end');
 ctx.manualResponse=null;ctx.flight={sample:t=>track.sample(t),segments:[segment],activeAt:()=>segment};ctx.simTime=track.returnEnd+2;vm.runInContext('out=targetPose()',ctx);
 assert(dist(ctx.out.points[10],aim.apply(reference,ctx.simTime,ctx.settings.target,1,false).points[10])<1e-8,'App holds timeline orientation after end');
 const nextName=name.startsWith('Kick')?'slashL':'KickL',nextStart=ctx.simTime,second=A.create({attack:nextName,attackIn:.2,attackOut:.25},{sample:()=>({pose:reference}),airStart:nextStart,jumpStart:nextStart,abortTime:Infinity},catalog,names,parents,settings,reference),previous=ctx.out;
 ctx.flight.segments.push({attack:second,event:{attack:nextName}});vm.runInContext('out=targetPose()',ctx);
 assert(dist(ctx.out.points[10],previous.points[10])<1e-8,'Next marker begins from retained orientation');
 ctx.settings.undoRotation=true;vm.runInContext('out=targetPose()',ctx);assert(dist(ctx.out.points[10],reference.points[10])<1e-8,'Toggling return on applies immediately');

}
assert(maxNativeCalibrationError<1e-9);assert(maxDirectionError<1e-6);assert(maxPelvisTilt<1e-8);assert(maxChainStepSpread<1e-8);assert(maxCOMError<1e-8);assert(maxLocalError<1e-8);assert(maxManualError<1e-6);
let savedScene=null;
if(process.argv.includes('--saved')){
 const stored=await (await fetch('http://127.0.0.1:8876/state')).json(),settings=stored.settings;
 assert.equal(settings.mode,'spaceGym');
 const run=I.create(read('data/idle.json'),bytes('data/idle.bin'),m).motion(settings.runPhase),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),flight=F.sequence(run,jumps,settings,parents,reference,null,catalog),segment=flight.segments.find(s=>s.attack),track=segment.attack,clip=catalog.get(segment.event.attack);
 const plan=Aim.create({clip,track,names,parents,reference,sampleHit:t=>track.sample(t).pose}),raw=track.sample(track.hitTime).pose;
 const result=amount=>{const pose=plan.apply(raw,track.hitTime,settings.target,amount),a=R.unit(R.sub(plan.point(pose),plan.origin)),b=R.unit(R.sub(settings.target,plan.origin));return {angleErrorDegrees:Math.acos(Math.max(-1,Math.min(1,R.dot(a,b))))*180/Math.PI,distance:dist(plan.point(pose),settings.target)};};
 savedScene={attack:clip.meta.name,target:settings.target,deadline:plan.deadline,yawDegrees:R.length(R.qlog(plan.correction(settings.target).yaw))*180/Math.PI,bendDegrees:Math.hypot(...plan.solution(settings.target).parameters.slice(1))*180/Math.PI,addedPelvisTiltDegrees:0,amount:settings.aimWeight,current:result(settings.aimWeight),full:result(1),reach:R.length(plan.direction),targetDistance:dist(settings.target,plan.origin)};
 assert(savedScene.full.angleErrorDegrees<1e-5);
}
assert.equal(C.sanitize({}).undoRotation,true);assert.equal(C.sanitize({undoRotation:false}).undoRotation,false);
const result={undoRotationChecks:meta.clips.length*2,samples,maxDirectionError,maxCOMError,maxLocalError,maxManualError,maxNativeCalibrationError,maxPelvisTilt,maxChainStepSpread,deadlines,savedScene,visualVerified:false};fs.writeFileSync(new URL('attack-aim-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(result);
