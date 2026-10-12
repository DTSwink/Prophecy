const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js'),FK=require('./armfk.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const dist=(a,b)=>R.length(R.sub(a,b));let cases=0,maxTip=0,maxEntry=0,maxAngular=0;
for(const motion of ['idle','walk'])for(const tolerance of [0,15,40])for(const correction of [.1,1]){
 const m=H.prepare(data,setup,{motion,sheathe:true,sheatheRotationTolerance:tolerance,slideRotationCorrection:correction,shrinkPercent:35,maxReachSpeed:250,maxReachRotationSpeed:2500,slidingSpeed:150});
 assert(m.plan.arrives);const p=m.plan,f=m.sourceFrames[p.endTick],mouth=H.point(H.seatedSword(setup,f.holster),setup.baseBladeLocal);
 const held=H.compose(H.scaledGrip(setup,f.scale),f.pose[m.arm[2]]);
 maxEntry=Math.max(maxEntry,dist(held.p,f.sword.p));assert(dist(held.p,f.sword.p)<1e-7);assert(H.angle(held.q,f.sword.q)<1e-5,'no orientation jump at ownership change');
 assert(dist(H.point(f.sword,m.tip),mouth)<=2);assert(H.angle(f.sword.q,H.seatedSword(setup,f.holster).q)<=tolerance+1e-5);
 for(const key of p.keys){const sample=FK.at(p,key.tick);for(let k=0;k<3;k++)assert(H.angle(sample.local[k].q,key.local[k].q)<1e-5,'fractional correction guide is reached exactly');}
 const initial=H.angle(f.sword.q,H.seatedSword(setup,f.holster).q);
 for(const fraction of [0,.01,.03,.05,.1,.3,.5,1]){
  const tick=p.endTick+(p.slideEnd-p.endTick)*fraction,frame=H.sampleBody(m,tick/60),full=H.seatedSword(setup,frame.holster);
  const expected=initial*(1-Math.min(1,fraction/correction)),err=Math.abs(H.angle(frame.sword.q,full.q)-expected);maxAngular=Math.max(maxAngular,err);assert(err<1e-4,'angle closes with slide progress, including fractional cutoff');
  const target=H.sheathSlideGoal(setup,frame.holster,frame.scale,m.tip,m.sheathEntry,fraction,correction),sword=H.compose(H.scaledGrip(setup,frame.scale),target);
  const tipError=dist(H.point(sword,m.tip),H.point(frame.sword,m.tip));maxTip=Math.max(maxTip,tipError);assert(tipError<1e-7);
 }
 const before=H.sampleBody(m,(p.endTick-1e-5)/60);assert(dist(before.sword.p,f.sword.p)<.01,'continuous reach/slide boundary');
 ++cases;
}
// The destination remains perfectly aligned; tolerance only permits early entry.
for(const motion of ['idle','walk']){
 const m=H.prepare(data,setup,{motion,sheathe:true}),p=m.plan;
 const perfect=H.prepare(data,setup,{motion,sheathe:true,sheatheRotationTolerance:0});
 assert(p.endTick<p.reachEndTick,'slide begins before the perfect reach finishes');
 for(const f of m.sourceFrames.slice(m.o.startTick,p.endTick)){
  assert.deepEqual(f.pose,perfect.sourceFrames[f.tick].pose,'tolerance must not change the aimed reach path');
  assert.equal(f.scale,perfect.sourceFrames[f.tick].scale,'tolerance must not retime shrink');
  const full=H.seatedSword(setup,f.holster),goalSword=H.compose(H.scaledGrip(setup,1-m.o.shrinkPercent/100),f.goal);
  assert(H.angle(goalSword.q,full.q)<1e-5,'reach aims for perfect rotation');
  const actual=H.compose(H.scaledGrip(setup,f.scale),f.pose[m.arm[2]]),mouth=H.point(full,setup.baseBladeLocal);
  assert(dist(H.point(actual,m.tip),mouth)>2||H.angle(actual.q,full.q)>m.o.sheatheRotationTolerance+1e-5,'cannot wait after both gates pass');
 }
 const entry=m.sourceFrames[p.endTick];
 for(const f of m.sourceFrames.slice(p.endTick,p.slideEnd+1)){
  assert.equal(f.body.applied[0],entry.body.applied[0],'accepted spine turn is preserved during insertion');
  assert(f.scale>=1-m.o.shrinkPercent/100-1e-12&&f.scale<=entry.scale+1e-12);
 }
 const corrected=H.sampleBody(m,(p.endTick+(p.slideEnd-p.endTick)*m.o.slideRotationCorrection)/60);
 assert(Math.abs(corrected.scale-(1-m.o.shrinkPercent/100))<1e-12,'residual shrink closes continuously by correction endpoint');
}
// Gaze modifies the underlying torso/arms while preserving every segment and lower body.
for(const yaw of [-170,-70,0,85,170])for(const motion of ['idle','walk']){
 const plain=H.motion(data,motion,.6),gaze=H.motion(data,motion,.6,yaw);
 if(!yaw)assert.deepEqual(gaze,plain);
 for(let j=0;j<data.names.length;j++){
  if(/^(root|pelvis|thigh|calf|foot|ball)/.test(data.names[j]))assert.deepEqual(gaze[j],plain[j]);
  if(data.parents[j]>=0)assert(Math.abs(dist(gaze[j].p,gaze[data.parents[j]].p)-dist(plain[j].p,plain[data.parents[j]].p))<1e-7);
 }
 if(yaw)assert(H.angle(plain[data.names.indexOf('clavicle_r')].q,gaze[data.names.indexOf('clavicle_r')].q)>1);
}
// Drawing ignores the S knobs; zero gaze is the unchanged authored base.
const a=H.prepare(data,setup,{sheathe:false}),b=H.prepare(data,setup,{sheathe:false,sheatheRotationTolerance:70,slideRotationCorrection:.8});assert.deepEqual(a.frames,b.frames);
assert.equal(H.sanitize({gazeYaw:999}).gazeYaw,170);assert.equal(H.sanitize({slideRotationCorrection:-2}).slideRotationCorrection,0);
console.log(JSON.stringify({passed:true,cases,maxEntryCm:maxEntry,maxTipCm:maxTip,maxAngleErrorDeg:maxAngular}));
