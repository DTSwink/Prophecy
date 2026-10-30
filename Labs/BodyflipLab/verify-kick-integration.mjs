import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),H=require('./attack-inertia.js'),A=require('./jump-attack.js'),K=require('./kick-attack.js'),B=require('./airborne-motion.js'),F=require('./flight.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),metadata=read('data/vanilla.json'),hinges=H.legHinges(names,reference),rig=H.model(names,parents,reference);
const app=fs.readFileSync(new URL('app.js',import.meta.url),'latin1'),manual=app.slice(app.indexOf('function manualPose('),app.indexOf('function targetPose('));
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),distance=(a,b)=>R.length(R.sub(a,b)),error=(a,b)=>Math.max(...a.q.map((q,i)=>angle(q,b.q[i])),...a.points.slice(1).map((p,i)=>distance(p,b.points[i+1]))),com=p=>B.center(H.bodies(p,rig),rig);
let samples=0,maxViewerError=0,maxEquivarianceError=0,maxCOMError=0,maxEndpointError=0,minKnee=Infinity,maxKnee=0;
const transform=(p,t)=>B.transform(p,R.qexp([.25*t,.5*t,-.17*t]),[0,0,0],[2*t,1+t,3*t]);
function inspect(p,base){
 assert(p.points.flat().every(Number.isFinite));maxCOMError=Math.max(maxCOMError,distance(com(p),com(base)));
 const a=R.localize(p.points,p.q,parents),b=R.localize(base.points,base.q,parents);
 // Root-to-pelvis offset may change to preserve COM; all real bone sockets stay fixed.
 for(let i=2;i<names.length;i++)assert(distance(a.p[i],b.p[i])<1e-8,'Fixed bone sockets');
 for(const h of hinges){const u=R.unit(R.sub(p.points[h.knee],p.points[h.hip])),v=R.unit(R.sub(p.points[h.foot],p.points[h.knee])),bend=Math.atan2(R.dot(R.cross(u,v),R.rotate(p.q[h.knee],h.kneeAxis)),R.dot(u,v));minKnee=Math.min(minKnee,bend);maxKnee=Math.max(maxKnee,bend);}
 samples++;
}
const directArmed=process.argv.includes('--armed'),started=performance.now(),clips=new Map();
for(const name of ['KickL','KickR','sweepKick']){
 const meta=metadata.clips.find(c=>c.name===name),clip=C.decode(meta,bytes(meta.file),names,parents);clips.set(name,clip);
 const start=.4,lead=.18,tail=.45,segment={sample:()=>({pose:reference}),airStart:start,jumpStart:start,abortTime:Infinity},e={attack:name,attackIn:lead,attackOut:tail};
 const timeline=A.create(e,segment,clips,names,parents,{...C.defaults,kickToArmed:directArmed},reference),viewer=K.preview({clip,names,parents,reference,directArmed}),moving=K.create({clip,names,parents,reference,base:t=>transform(reference,t),start,lead,tail,directArmed});
 if(directArmed){
  const tr=viewer.track;assert.equal(tr.lead,Math.max(lead,meta.phases.armed/meta.fps));
  assert.equal(tr.sourceStart,meta.phases.armed);
  assert(Math.abs(timeline.hitTime-timeline.armedTime-(meta.phases.hit-meta.phases.armed)/meta.fps)<1e-10,'Native Armed to Hit timing');
  assert(error(tr.sample(tr.lead),tr.at(meta.phases.armed))<1e-9,'Direct endpoint is the actual Armed pose');
  for(let f=meta.phases.armed;f<=meta.frames-1;f+=.25)assert(error(tr.sample(tr.lead+(f-meta.phases.armed)/meta.fps),tr.at(f))<1e-8,'Complete recorded motion after Armed');
  // Local angular velocity joins the recorded motion, with no stop at Armed.
  const eps=1e-6,local=t=>R.localize(tr.sample(t).points,tr.sample(t).q,parents).q;
  const a=local(tr.lead-eps),b=local(tr.lead),c=local(tr.lead+eps);
  for(let i=0;i<names.length;i++)assert(distance(R.mul(R.qlog(R.qm(b[i],R.qinv(a[i]))),1/eps),R.mul(R.qlog(R.qm(c[i],R.qinv(b[i]))),1/eps))<.03,'Armed velocity continuity');
  const original=K.preview({clip,names,parents,reference});assert.notEqual(original,viewer,'Mode has a separate cache');
  const slow=B.recording({clip,names,parents,reference,lead:.7,directArmed:true});assert.equal(slow.armedTime,.7,'Longer In setting remains respected');
 }
 assert(timeline.fullBodyKick);assert.equal(timeline.plan,viewer,'Timeline uses the cached viewer plan');
 for(let t=0;t<viewer.track.stop+.1;t+=1/120){const p=timeline.sample(start+t).pose,want=viewer.response.sample(t);maxViewerError=Math.max(maxViewerError,error(p,want));const carried=moving.sample(start+t);maxEquivarianceError=Math.max(maxEquivarianceError,error(carried,transform(p,start+t)));inspect(p,reference);inspect(carried,transform(reference,start+t));}
 for(const t of [timeline.start,timeline.returnEnd,timeline.returnEnd+.3])maxEndpointError=Math.max(maxEndpointError,error(timeline.sample(t).pose,reference));
 const saved=JSON.stringify(timeline.sample(timeline.hitTime));timeline.sample(0);timeline.sample(100);assert.equal(JSON.stringify(timeline.sample(timeline.hitTime)),saved);
 for(const rate of [.5,1,2]){
  // Actual Attack-button functions, including missing variant name/phases metadata.
  const group=m.clips.find(c=>c.name===name),variant=group.variants[0],selected=C.decode(variant,bytes(variant.file),names,parents);
  const ctx=vm.createContext({R,C,BodyflipJumpAttack:A,BodyflipKickAttack:K,BodyflipAttackInertia:H,clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),names,parents,idle:reference,clip:selected,settings:{...C.defaults,kickToArmed:directArmed,attack:name,attackRate:rate,aim:true},flight:{sample:t=>({pose:transform(reference,t)})},vanillaManifest:metadata,manualResponse:null,simTime:0,attackTime:0});vm.runInContext(manual,ctx);
  for(let t=0;t<selected.duration+.7;t+=1/60){ctx.simTime=t/rate;ctx.attackTime=t;ctx.basePose=transform(reference,t/rate);vm.runInContext('output=manualSoft(manualPose(attackTime,basePose),basePose)',ctx);assert(ctx.manualResponse.response.fullBodyKick);const plan=ctx.manualResponse.response.plan;maxViewerError=Math.max(maxViewerError,error(ctx.output,transform(plan.response.sample(t),t/rate)));inspect(ctx.output,ctx.basePose);}
 }
}
const run=F.decodeNN(read('data/run-default-drawn.json')),base=t=>{const f=Math.max(0,Math.min(run.poses.length-1,t*run.fps)),i=Math.min(run.poses.length-2,Math.floor(f));return C.blend(run.poses[i],run.poses[i+1],f-i,parents);};
for(const clip of clips.values()){
 const kick=K.create({clip,names,parents,reference,base,start:.3,lead:.2,tail:.25,directArmed});
 for(let t=.3;t<kick.returnEnd+.1;t+=1/120)inspect(kick.sample(t),base(t));
 for(const t of [kick.start,kick.returnEnd])maxEndpointError=Math.max(maxEndpointError,error(kick.sample(t),base(t)));
 assert(error(kick.sample(kick.start+1e-7),base(kick.start+1e-7))<1e-5,'Entry continuity on gait');
 assert(error(kick.sample(kick.returnEnd-1e-7),base(kick.returnEnd-1e-7))<1e-5,'Exit continuity on gait');
}
// Repeat markers reuse a plan, rather than repeating the numerical solve.
const clip=clips.get('KickL'),before=performance.now();for(let i=0;i<32;i++)K.create({clip,names,parents,reference,base:()=>reference,start:i,lead:.18,tail:.45,directArmed}).sample(i+.6);const repeatedMs=performance.now()-before;
assert(maxViewerError<1e-8);assert(maxEquivarianceError<1e-8);assert(maxCOMError<1e-8);assert(maxEndpointError<1e-8);assert(minKnee>=-1e-5&&maxKnee<150*Math.PI/180,'Hinged knees without inversion/overfold');assert(repeatedMs<500);
const result={directArmed,samples,maxViewerError,maxEquivarianceError,maxCOMError,maxEndpointError,kneeDegrees:[minKnee,maxKnee].map(x=>x*180/Math.PI),repeatedMs,elapsedMs:performance.now()-started};fs.writeFileSync(new URL(directArmed?'kick-armed-verification.json':'kick-integration-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(result);
