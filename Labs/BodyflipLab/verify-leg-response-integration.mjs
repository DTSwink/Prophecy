import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),H=require('./attack-inertia.js'),L=require('./leg-response.js'),A=require('./jump-attack.js'),I=require('./idle.js'),F=require('./flight.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),buf=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),ref=C.poseFromShared(m),idle=I.create(read('data/idle.json'),buf('data/idle.bin'),m).motion(),metadata=read('data/vanilla.json'),upper=A.bones(m.names,m.parents),hinges=H.legHinges(m.names,ref),qerror=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
const app=fs.readFileSync(new URL('app.js',import.meta.url),'latin1'),manual=app.slice(app.indexOf('function manualPose('),app.indexOf('function targetPose('));
let maxUpperError=0,maxParityError=0,minKnee=Infinity,maxKnee=-Infinity,samples=0;
function inspect(p,raw){
 assert(p.points.flat().every(Number.isFinite));
 for(const i of upper)maxUpperError=Math.max(maxUpperError,qerror(p.q[i],raw.q[i]));
 for(const h of hinges){const a=R.unit(R.sub(p.points[h.knee],p.points[h.hip])),b=R.unit(R.sub(p.points[h.foot],p.points[h.knee])),bend=Math.atan2(R.dot(R.cross(a,b),R.rotate(p.q[h.knee],h.kneeAxis)),R.dot(a,b));minKnee=Math.min(minKnee,bend);maxKnee=Math.max(maxKnee,bend);}
 samples++;
}
// Exercise the actual Attack-button functions without a browser, writes or NN.
for(const group of m.clips){
 const meta=group.variants[0],clip=C.decode(meta,buf(meta.file),m.names,m.parents),base=t=>({pose:idle.sample(t)});
 const ctx=vm.createContext({R,C,BodyflipJumpAttack:A,BodyflipAttackInertia:H,clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),names:m.names,parents:m.parents,idle:ref,clip,settings:{...C.defaults,attack:group.name,aim:false,pelvisAttackCompensation:1},flight:{sample:base},vanillaManifest:metadata,manualResponse:null,simTime:0,attackTime:0});
 vm.runInContext(manual,ctx);
 for(let t=0;t<clip.duration+1.6;t+=1/60){
  ctx.simTime=ctx.attackTime=t;ctx.basePose=base(t).pose;
  vm.runInContext('raw=manualPose(attackTime,basePose); output=manualSoft(raw,basePose)',ctx);
  assert(ctx.manualResponse.response.legResponse,'Manual attack uses whole-leg response');inspect(ctx.output,ctx.raw);
 }
}
// Viewer and app both use A.create's spatial planner and single shared response.
const meta=metadata.clips.find(c=>c.name==='slashL'),clip=C.decode(meta,buf(meta.file),m.names,m.parents),catalog=new Map([['slashL',clip]]),base=t=>({pose:idle.sample(t)}),segment={sample:base,airStart:.35,jumpStart:.35,abortTime:Infinity},settings={...C.defaults,pelvisAttackCompensation:1};
const current=A.create({attack:'slashL'},segment,catalog,m.names,m.parents,settings,ref);
assert.equal(current.inertia.diagnostics.axes,3);
const referenceResponse=L.create({source:t=>current.inertia.samplePlanned(t),base:t=>base(t).pose,start:current.start,stop:current.end+.25+1,names:m.names,parents:m.parents,reference:ref,hinges,anticipation:.06,sampleRate:60});
for(let t=0;t<3;t+=1/120){const a=referenceResponse.sample(t),b=current.sample(t).pose;for(let i=0;i<m.names.length;i++)maxParityError=Math.max(maxParityError,qerror(a.q[i],b.q[i]),R.length(R.sub(a.points[i],b.points[i])));}
// Continuing NN articulation plus whole-character rotation must not redirect
// the response in world space or create a backward-bending knee.
const run=F.decodeNN(read('data/run-default-drawn.json'));
const runAt=t=>{const f=Math.max(0,Math.min(run.poses.length-1,t*run.fps)),i=Math.min(run.poses.length-2,Math.floor(f));return C.blend(run.poses[i],run.poses[i+1],f-i,m.parents);};
const rotation=R.qexp([.6,-.3,.2]),shift=[1,2,3],transform=p=>({points:p.points.map(v=>R.add(R.rotate(rotation,v),shift)),q:p.q.map(q=>R.qm(rotation,q))});
const moving={...segment,sample:t=>({pose:runAt(t)})},tilted={...segment,sample:t=>({pose:transform(runAt(t))})};
const a=A.create({attack:'slashL'},moving,catalog,m.names,m.parents,settings,ref),b=A.create({attack:'slashL'},tilted,catalog,m.names,m.parents,settings,ref),raw=A.create({attack:'slashL'},moving,catalog,m.names,m.parents,{...settings,pelvisAttackCompensation:0},ref);
let maxEquivarianceError=0;
for(let t=.35;t<2.4;t+=1/120){const p=a.sample(t).pose,q=b.sample(t).pose,want=transform(p);inspect(p,raw.sample(t).pose);for(let i=0;i<m.names.length;i++)maxEquivarianceError=Math.max(maxEquivarianceError,qerror(q.q[i],want.q[i]),R.length(R.sub(q.points[i],want.points[i])));}
assert(maxUpperError<1e-9);assert(maxParityError<1e-9);assert(maxEquivarianceError<1e-8);assert(minKnee>=-1e-4&&maxKnee<Math.PI*150/180,'No knee inversion/overfold on continuing gait');
const result={manualAttacks:m.clips.length,samples,maxUpperError,maxParityError,maxEquivarianceError,minKnee,maxKnee};fs.writeFileSync(new URL('leg-response-integration-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(result);
