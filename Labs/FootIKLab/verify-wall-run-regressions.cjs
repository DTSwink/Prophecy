'use strict';
// Exact saved wall-run regression. Reads recorded NN inputs and before/after
// poses; no inference, server, UI writes or background processes.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),z=require('node:zlib'),Module=require('node:module');
const R=require('./recovery.js'),K=require('./footik.js'),C=require('./surface-coupling.js'),J=require('./slide-joints.js'),A=require('./verify-slide-arm-clearance.cjs'),Bank=require('./test-bank.cjs');
const dir=path.resolve(process.argv[2]||path.join(__dirname,'../../Saved/Diagnostics/FootIKWall20261103'));
const read=name=>JSON.parse(z.gunzipSync(fs.readFileSync(path.join(dir,name))));
let checks=0;const check=(ok,message)=>{assert.ok(ok,message);checks++;};
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI;
const relative=(f,j)=>R.sub(f.pose.points[j],f.pose.points[1]);
function motion(m,bone,start,end){
 const j=m.names.indexOf(bone);let step=0,acceleration=0,travel=0;
 for(let i=Math.max(2,start*2);i<=Math.min(m.frames.length-1,end*2);i++){
  const f=m.frames,delta=R.sub(relative(f[i],j),relative(f[i-1],j)),prior=R.sub(relative(f[i-1],j),relative(f[i-2],j));
  step=Math.max(step,angle(f[i].pose.q[j],f[i-1].pose.q[j]));acceleration=Math.max(acceleration,R.length(R.sub(delta,prior))*14400);travel+=R.length(delta);
 }return {step,acceleration,travel};
}
(async()=>{
 const before=read('before.model.json.gz'),after=read('final.model.json.gz'),fixture=read('final.fixture.json.gz'),original=read('current.fixture.json.gz'),joints=J.build(undefined,after.names,after.parents);
 // The user may move the camera/playhead while these captures run.
 assert.deepEqual(fixture.saved.settings,original.saved.settings);checks++;
 let addedAnkleLimit=0,pinDrift=0,contacts=0;
 for(const f of after.frames){
  check(f.pose.points.flat().every(Number.isFinite)&&f.pose.q.flat().every(Number.isFinite),'Finite pose');
  if(!f.slide)for(const side of ['l','r']){const j=after.names.indexOf('foot_'+side),parent=after.parents[j];addedAnkleLimit=Math.max(addedAnkleLimit,joints.project(j,f.pose.q[parent],f.pose.q[j]).correctionRad-joints.project(j,f.raw.q[parent],f.raw.q[j]).correctionRad);}
  for(const foot of f.feet)if(foot.contact){const j=after.names.indexOf('foot_'+foot.side.toLowerCase()),c=foot.contact;contacts++;pinDrift=Math.max(pinDrift,R.length(R.sub(R.add(f.pose.points[j],R.rotate(f.pose.q[j],c.localPoint)),c.point)));}
 }
 check(addedAnkleLimit<1e-6,'Terrain solve introduces no ankle-limit violation beyond source NN');
 check(contacts>0&&pinDrift<1e-8,'Material pin remains exact');
 check(after.frames.slice(36,40).some(f=>f.feet.some(x=>x.side==='R'&&x.contact)),'First right wall step still acquires contact');
 const kneeBefore=motion(before,'calf_r',18,21),kneeAfter=motion(after,'calf_r',18,21);
 check(kneeAfter.step<kneeBefore.step*.65,'Contact/release avoids the near-straight knee snap');
 const windows=[[63,70],[81,88]],hands=windows.map(([start,end])=>({start,end,before:motion(before,'hand_r',start,end),after:motion(after,'hand_r',start,end)}));
 for(const h of hands)check(h.after.acceleration<20&&h.after.acceleration<h.before.acceleration*.2,'Reported right-hand kick removed');
 const travel=['hand_l','hand_r'].map(bone=>({bone,before:motion(before,bone,46,132).travel,after:motion(after,bone,46,132).travel}));
 for(const t of travel)check(t.after>t.before*.9,'Do not hide the hitch by suppressing arm travel');
 const settled=after.frames.slice(160).filter(f=>f.slide);
 check(settled.length>0&&settled.every(f=>f.slide.hands.some(h=>h.touching)),'At least one hand keeps wall contact after entry');
 const arms=A.measure(after);check(arms.minGap>=-.0001,'Actual arm capsules and hand boxes clear the wall');
 // Split preparation must reproduce one chronological solve. The fixture
 // contains genuine policy replies for this exact source/settings version.
 const run=K.decode(fixture.request.source,after.parents),make=()=>C.createSession(run,fixture.request.settings,async(_,i)=>{const v=fixture.response.steps[i];assert.ok(v,'Recorded NN stream exhausted');return v;}),whole=make(),split=make();
 try{
  await whole.extend(2.2);
  for(const end of [.1,.31,.46,.9,1.1,1.5,2.2]){const prefix=split.model.frames.map(f=>JSON.stringify(f));await split.extend(end);prefix.forEach((f,i)=>check(JSON.stringify(split.model.frames[i])===f,'Extension does not mutate completed frames'));}
  assert.deepEqual(split.model.frames,whole.model.frames);checks++;
 }finally{whole.close();split.close();}
 // Surface contact work must leave the separate ordinary stair/flat solver
 // exactly unchanged, including disabled behavior.
 const old=new Module(path.join(__dirname,'footik-before-test.js'),module);old.filename=path.join(__dirname,'footik-before-test.js');old.paths=module.paths;old._compile(fs.readFileSync(path.join(dir,'before-footik.js'),'utf8'),old.filename);
 for(const gait of ['walk','run']){const bank=Bank.load(gait,.21);for(const terrain of ['flat','stairs','down']){const s={gait,terrain};assert.deepEqual(K.prepare(bank,s).frames,old.exports.prepare(bank,s).frames);checks++;}assert.deepEqual(K.prepare(bank,{gait,enabled:false}).frames,old.exports.prepare(bank,{gait,enabled:false}).frames);checks++;}
 const report={passed:true,checks,frames:after.frames.length,addedAnkleLimitDeg:addedAnkleLimit*180/Math.PI,pinDrift,kneeBefore,kneeAfter,hands,travel,arms};
 fs.writeFileSync(path.join(dir,'verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
