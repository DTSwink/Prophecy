import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),H=require('./attack-inertia.js'),A=require('./jump-attack.js'),F=require('./flight.js');
const dir=path.dirname(fileURLToPath(import.meta.url)),before=path.resolve(dir,'../../Saved/BodyflipLab/AllAttackHitReturn/Before');
const read=p=>JSON.parse(fs.readFileSync(path.join(dir,p),'utf8')),bytes=p=>{const b=fs.readFileSync(path.join(dir,p));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),metadata=read('data/vanilla.json'),hinges=H.legHinges(names,reference),limit=150*Math.PI/180;
// An optional local pre-change snapshot adds independent strike parity to the
// portable recovery checks; it is not needed to run these tests elsewhere.
const hasBefore=fs.existsSync(path.join(before,'jump-attack.js'))&&fs.existsSync(path.join(before,'app.js')),context=vm.createContext({module:{exports:{}},require:p=>require(path.join(dir,p))});if(hasBefore)vm.runInContext(fs.readFileSync(path.join(before,'jump-attack.js'),'utf8'),context);const oldA=hasBefore?context.module.exports:null;
const manualCode=p=>{const s=fs.readFileSync(p,'latin1');return s.slice(s.indexOf('function manualPose('),s.indexOf('function targetPose('));},manual=manualCode(path.join(dir,'app.js')),oldManual=hasBefore?manualCode(path.join(before,'app.js')):null;
const run=F.decodeNN(read('data/run-default-drawn.json')),base=t=>{const f=Math.max(0,Math.min(run.poses.length-1,t*run.fps)),i=Math.min(run.poses.length-2,Math.floor(f));return C.blend(run.poses[i],run.poses[i+1],f-i,parents);};
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),error=(a,b)=>Math.max(...a.q.map((q,i)=>angle(q,b.q[i])),...a.points.map((p,i)=>distance(p,b.points[i])));
const bend=(p,h)=>{const a=R.unit(R.sub(p.points[h.knee],p.points[h.hip])),b=R.unit(R.sub(p.points[h.foot],p.points[h.knee]));return Math.atan2(R.dot(R.cross(a,b),R.rotate(p.q[h.knee],h.kneeAxis)),R.dot(a,b));};
const modes=[{softAttackLegs:true,pelvisAttackCompensation:1},{softAttackLegs:false,pelvisAttackCompensation:1},{softAttackLegs:true,pelvisAttackCompensation:0}];
let maxFollowthroughError=0,maxStrikeError=0,maxHitJoinError=0,maxEndpointError=0,maxBacktrack=0,minKnee=Infinity,maxKnee=0,samples=0;
const cases=[];
function inspect(sample,baseline,hit,end,original){
 const bHit=sample(hit),eps=1e-7;maxHitJoinError=Math.max(maxHitJoinError,error(bHit,sample(hit+eps)));
 let previous=null;
 for(let t=hit;t<end;t+=1/120){
  const pose=sample(t),rest=baseline(t),local=R.localize(pose.points,pose.q,parents),baseLocal=R.localize(rest.points,rest.q,parents),errors=local.q.map((q,i)=>angle(q,baseLocal.q[i]));
  for(const h of hinges){const a=bend(pose,h),b=bend(rest,h),delta=a-b,room=delta<0?b:limit-b;minKnee=Math.min(minKnee,a);maxKnee=Math.max(maxKnee,a);errors[h.knee]=room>.005?Math.abs(delta)/room:null;}
  const p=names.indexOf('pelvis');if(previous)maxBacktrack=Math.max(maxBacktrack,errors[p]-previous[p]);if(original){const old=original(t);for(let i=0;i<names.length;i++)if(i!==p)maxFollowthroughError=Math.max(maxFollowthroughError,angle(pose.q[i],old.q[i]));}
  previous=errors;for(let i=1;i<names.length;i++)assert(distance(local.p[i],baseLocal.p[i])<1e-8,'No changing sockets');samples++;
 }
 for(const t of [end,end+.2,end+1])maxEndpointError=Math.max(maxEndpointError,error(sample(t),baseline(t)));
 const time=hit+(end-hit)*.37,saved=JSON.stringify(sample(time));sample(end+1);sample(0);assert.equal(JSON.stringify(sample(time)),saved,'Reverse seek is deterministic');
}
for(const meta of metadata.clips.filter(c=>!C.effector(c.name).startsWith('foot_'))){
 const clip=C.decode(meta,bytes(meta.file),names,parents),catalog=new Map([[meta.name,clip]]),segment={sample:t=>({pose:base(t)}),airStart:.35,jumpStart:.35,abortTime:Infinity};
 for(const mode of modes){
  const settings={...C.defaults,...mode},event={attack:meta.name},track=A.create(event,segment,catalog,names,parents,settings,reference),old=oldA?.create(event,segment,catalog,names,parents,settings,reference);
  if(old)assert.equal(track.end,old.end);assert.equal(track.returnEnd,track.end+C.sanitizeJump(event).attackOut);assert.equal(track.recovery.start,track.hitTime);
  if(old)for(let i=0;i<=12;i++){const t=track.start+(track.hitTime-track.start)*i/12;maxStrikeError=Math.max(maxStrikeError,error(track.sample(t).pose,old.sample(t).pose));}
  inspect(t=>track.sample(t).pose,base,track.hitTime,track.returnEnd,old?t=>old.sample(t).pose:null);
  cases.push({path:'timeline',attack:meta.name,...mode});
 }
}
// Kick viewer/app parity is checked in verify-kick-integration.mjs.
for(const group of m.clips.filter(c=>!C.effector(c.name).startsWith('foot_'))){
 const meta=group.variants[0],clip=C.decode(meta,bytes(meta.file),names,parents);
 for(const [modeIndex,mode] of modes.entries()){
  const rate=[.5,1,2][modeIndex],settings={...C.defaults,...mode,attack:group.name,attackRate:rate,aim:false,airFlip:false},make=(code,api)=>{const ctx=vm.createContext({R,C,BodyflipJumpAttack:api,BodyflipKickAttack:require('./kick-attack.js'),BodyflipAttackInertia:H,clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),names,parents,idle:reference,clip,settings,flight:{sample:t=>({pose:base(t)})},vanillaManifest:metadata,manualResponse:null,simTime:0,attackTime:0});vm.runInContext(code,ctx);return ctx;},ctx=make(manual,A),old=hasBefore?make(oldManual,oldA):null;
  const sample=(context,t)=>{context.simTime=t/rate;context.attackTime=t;context.basePose=base(t/rate);vm.runInContext('output=manualSoft(manualPose(attackTime,basePose),basePose)',context);return context.output;};
  sample(ctx,0);const response=ctx.manualResponse.response,hit=response.hitTime,end=response.returnEnd;
  assert.equal(end,clip.duration+.6);assert.equal(response.recovery.start,hit);
  if(old)for(let i=0;i<=12;i++){const t=hit*i/12;maxStrikeError=Math.max(maxStrikeError,error(sample(ctx,t),sample(old,t)));}
  inspect(t=>sample(ctx,t),t=>base(t/rate),hit,end,old?t=>sample(old,t):null);
  cases.push({path:'manual',attack:group.name,rate,...mode});
 }
}
assert.equal(cases.length,84);assert(maxStrikeError<1e-8,'All attacks keep their original motion through Hit');
assert(maxHitJoinError<1e-5,'No pose discontinuity at Hit');assert(maxEndpointError<1e-8,'Settle at original end time');
assert(maxBacktrack<1e-7,'Pelvis correction never reverses away from the continuing baseline');assert(maxFollowthroughError<1e-8,'Every non-pelvis world orientation retains original follow-through');assert(minKnee>=-1e-5&&maxKnee<=limit+1e-5,'No knee inversion or overfold');
const result={cases:cases.length,samples,maxFollowthroughError,strikeComparedWithSnapshot:hasBefore,maxStrikeError:hasBefore?maxStrikeError:null,maxHitJoinError,maxEndpointError,maxBacktrack,kneeRangeDegrees:[minKnee,maxKnee].map(v=>v*180/Math.PI),checked:cases};
fs.writeFileSync(path.join(dir,'all-attack-hit-return-verification.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({...result,checked:undefined},null,2));
