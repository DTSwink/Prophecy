const fs=require('node:fs'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const R=require('./recovery.js'),manifest=JSON.parse(fs.readFileSync(__dirname+'/data/manifest.json'));
const maxDiff=(a,b)=>Math.max(...a.flat(Infinity).map((x,i)=>Math.abs(x-b.flat(Infinity)[i])));
const errorStats={motions:0,floorMotions:0,maxLengthError:0,maxLowerError:0,maxIdleAngle:0,maxSeamPositionError:0};
assert.equal(manifest.clips.length,16);
for(const clip of manifest.clips){
 assert.equal(clip.variants.length,20);assert.equal(clip.variants.filter(v=>v.kind==='floor').length,clip.name==='headbutt'?0:1);
 const targets=new Set(clip.variants.map(v=>JSON.stringify(v.target)));assert.equal(targets.size,20);
 for(const v of clip.variants){
  const b=fs.readFileSync(__dirname+'/'+v.file);assert.equal(crypto.createHash('sha256').update(b).digest('hex'),v.sha256);
  const model=R.prepare(v,b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),clip,manifest.names,manifest.parents);
  assert(clip.phases.armed<clip.phases.hit&&clip.phases.hit<v.frames);
  const end=model.poses.at(-1),localEnd=model.locals.at(-1);
  for(let f=0;f<v.frames;f++) assert.deepEqual(R.sample(model,f/v.fps).points,model.poses[f].points,'authored frame changed');
  for(const duration of [.1,1,3])for(const inertia of [0,.35,1]){
   const opt={enabled:true,duration,inertia};
   assert.equal(R.sample(model,model.attackSeconds+1,{...opt,enabled:false}),end,'disabled processing');
   for(const fraction of [1e-6,.1,.3,.7,.9999,1,2]){
    const pose=R.sample(model,model.attackSeconds+fraction*duration,opt);
    assert(pose.points.flat().every(Number.isFinite));assert(pose.axes.flat(2).every(Number.isFinite));
    for(let j=0;j<manifest.names.length;j++){
     if(!model.upper[j]){const error=R.length(R.sub(pose.points[j],end.points[j]));errorStats.maxLowerError=Math.max(errorStats.maxLowerError,error);assert(error<2e-6,'lower body changed');}
     if(model.upper[j]){const parent=manifest.parents[j];const error=Math.abs(R.length(R.sub(pose.points[j],pose.points[parent]))-R.length(localEnd.p[j]));errorStats.maxLengthError=Math.max(errorStats.maxLengthError,error);assert(error<1e-7,'segment length changed');}
    }
    const anchored=R.anchor(model,pose,v.target);assert(R.length(R.sub(anchored.points[model.spine],model.poses[0].points[model.spine]))<1e-12,'spine lock');
   }
   const seam=R.sample(model,model.attackSeconds+1e-8,opt);const seamError=Math.max(...seam.points.map((p,j)=>R.length(R.sub(p,end.points[j]))));errorStats.maxSeamPositionError=Math.max(errorStats.maxSeamPositionError,seamError);assert(seamError<3e-6,'tail position jump');
   const idle=R.sample(model,model.attackSeconds+duration,opt),local=R.localize(idle.points,idle.q,manifest.parents);
   for(let j=0;j<model.upper.length;j++)if(model.upper[j]){const angle=R.length(R.qlog(R.qm(R.qinv(model.idle.q[j]),local.q[j])));errorStats.maxIdleAngle=Math.max(errorStats.maxIdleAngle,angle);assert(angle<1e-8,'did not reach parent-local idle');}
   const late=R.sample(model,model.attackSeconds+duration+5,opt);assert(maxDiff(idle.points,late.points)<1e-12,'completed recovery moved');
  }
  // Visible world velocity is continuous, rather than multiplied down the chain.
  // Include easing's initial velocity and parents with no inertia of their own.
  for(const returnEasing of [0,.12,1])for(const boneInertia of [{},{spine:0,clavicle:0,upperarm:1,lowerarm:.61}]){
   const dt=1e-7,opt={duration:.26,inertia:1,returnEasing,boneInertia},pose=R.sample(model,model.attackSeconds+dt,opt);
   for(let j=0;j<model.upper.length;j++)if(model.inertial[j]&&(boneInertia[model.inertiaKeys[j]]??1)>0){const actualWorld=R.mul(R.qlog(R.qm(pose.q[j],R.qinv(end.q[j]))),1/dt);assert(R.length(R.sub(actualWorld,model.worldVelocity[j]))<.002,'visible world angular velocity mismatch');}
  }
  for(const inertiaHold of [0,.25,.8])for(const inertiaDecay of [0,1,4]){
   const opt={duration:.31,inertia:1,inertiaHold,inertiaDecay,returnEasing:.12},dt=1e-7;
   const first=R.sample(model,model.attackSeconds+dt,opt);
   for(let j=0;j<model.upper.length;j++)if(model.inertial[j]){const w=R.mul(R.qlog(R.qm(first.q[j],R.qinv(end.q[j]))),1/dt);assert(R.length(R.sub(w,model.worldVelocity[j]))<.005,'timing knob broke outgoing velocity');}
   for(const fraction of [.1,.5,.9,.999999]){const pose=R.sample(model,model.attackSeconds+fraction*opt.duration,opt);assert(pose.points.flat().every(Number.isFinite));for(let j=0;j<model.upper.length;j++){if(!model.upper[j])assert(R.length(R.sub(pose.points[j],end.points[j]))<1e-8);else assert(Math.abs(R.length(R.sub(pose.points[j],pose.points[model.parents[j]]))-R.length(localEnd.p[j]))<1e-8);}}
   assert.strictEqual(R.sample(model,model.attackSeconds+opt.duration,opt),model.idlePose,'timing knob missed idle deadline');
   if(inertiaHold>0){const t=model.attackSeconds+inertiaHold*opt.duration,a=R.sample(model,t-dt,opt),b=R.sample(model,t,opt),c=R.sample(model,t+dt,opt);for(let j=0;j<model.upper.length;j++)if(model.inertial[j]){const before=R.mul(R.qlog(R.qm(b.q[j],R.qinv(a.q[j]))),1/dt),after=R.mul(R.qlog(R.qm(c.q[j],R.qinv(b.q[j]))),1/dt);assert(R.length(R.sub(before,after))<.01,'hold release velocity jump');}}
  }
  for(const part of [.1,.4,.8]){
   const a=R.sample(model,model.attackSeconds+part,{duration:1,inertia:0}),b=R.sample(model,model.attackSeconds+part,{duration:1,inertia:1});
   const la=R.localize(a.points,a.q,manifest.parents),lb=R.localize(b.points,b.q,manifest.parents);
   for(const name of ['hand_l','hand_r']){const j=manifest.names.indexOf(name);assert(R.length(R.qlog(R.qm(R.qinv(la.q[j]),lb.q[j])))<1e-10,'local hand orientation has inertia');assert(R.length(R.sub(la.p[j],lb.p[j]))<1e-10,'local hand position has inertia');}
  }
  // Every fractional authored basis must follow the global shortest arc,
  // irrespective of a compensating parent roll across the quaternion seam.
  for(let f=0;f<v.frames-1;f++)for(const part of [.01,.5,.99]){
   const pose=R.sample(model,(f+part)/v.fps);
   for(let j=0;j<manifest.names.length;j++){if(model.arms.some(a=>a.bone===j))continue;const expected=R.qslerp(model.poses[f].q[j],model.poses[f+1].q[j],part);assert(R.length(R.qlog(R.qm(R.qinv(expected),pose.q[j])))<1e-9,'authored subframe orientation changed');}
  }
  for(let f=0;f<v.frames-1;f++)for(const part of [0,.5]){
   const pose=R.sample(model,(f+part)/v.fps);
   for(const arm of model.arms){const actual=R.unit(R.sub(pose.points[arm.hand],pose.points[arm.bone]));assert(R.length(R.sub(R.rotate(pose.q[arm.bone],arm.axis),actual))<1e-6,'forearm frame does not follow wrist');}
  }
  errorStats.motions++;if(v.kind==='floor'){errorStats.floorMotions++;assert(Math.abs(v.target[1])<1e-6,'floor target not on floor');}
 }
}
const clip=manifest.clips.find(c=>c.name==='slashLU'),v=clip.variants[19],b=fs.readFileSync(__dirname+'/'+v.file);
const model=R.prepare(v,b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),clip,manifest.names,manifest.parents);
const regression=JSON.parse(fs.readFileSync(__dirname+'/audit-snapshot-0002.json'));
errorStats.snapshot2HandErrorDeg=0;
for(const row of regression.rows){const pose=R.sample(model,row.frame/v.fps);const angle=R.length(R.qlog(R.qm(R.qinv(R.fromAxes(row.sourceHandAxes)),pose.q[14])))*180/Math.PI;errorStats.snapshot2HandErrorDeg=Math.max(errorStats.snapshot2HandErrorDeg,angle);assert(angle<.0001,'snapshot 2 sword regression');}
let t0=performance.now();for(let i=0;i<10000;i++)R.sample(model,model.attackSeconds+.4,{duration:1,inertia:.35});
errorStats.averageRecoveryMicroseconds=(performance.now()-t0)*1000/10000;
fs.writeFileSync(__dirname+'/verification-core.json',JSON.stringify(errorStats,null,2));console.log(JSON.stringify(errorStats,null,2));
