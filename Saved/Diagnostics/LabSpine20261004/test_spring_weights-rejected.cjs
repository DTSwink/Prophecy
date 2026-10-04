const fs=require('fs'),assert=require('assert/strict'),R=require('./recovery.js'),manifest=JSON.parse(fs.readFileSync(__dirname+'/data/manifest.json'));
let cases=0,maxZeroLimitAngle=0;
for(const clip of manifest.clips){const v=clip.variants[15],bytes=fs.readFileSync(__dirname+'/'+v.file),model=R.prepare(v,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length),clip,manifest.names,manifest.parents);
 for(const worldInertia of [false,true]){
  const base={duration:.27,inertia:1,springReturn:true,worldInertia,inertiaDecay:0,returnEasing:0};
  for(const weight of [0,1e-6,.01,.04,.05,.1,1]){
   const o={...base,inertia:weight};R.sample(model,model.attackSeconds+.05,o);
   for(let j=0;j<model.names.length;j++)if(model.inertial[j])assert(R.length(R.sub(model.springCache.initialWorld[j],R.mul(model.worldVelocity[j],weight)))<1e-9,'inherited momentum counted twice');
   const end=R.sample(model,model.attackSeconds+o.duration,o);assert.strictEqual(end,model.idlePose);
   // With all outgoing velocities removed, the pull must be identical for
   // every weight. A mass/stiffness interpretation would violate this.
   const stationary={...model,worldVelocity:model.worldVelocity.map(()=>[0,0,0]),offsetVelocity:model.offsetVelocity.map(()=>[0,0,0]),springCache:null,seedCache:null};
   const low=R.sample(stationary,model.attackSeconds+.13,o),full=R.sample(stationary,model.attackSeconds+.13,{...base,inertia:1});assert.deepEqual(low,full,'inertia changed spring attraction');cases++;
  }
  for(const t of [.01,.05,.1,.15,.25]){
   const a=R.sample(model,model.attackSeconds+t,{...base,inertia:0}),b=R.sample(model,model.attackSeconds+t,{...base,inertia:1e-6});
   for(let j=0;j<model.names.length;j++)maxZeroLimitAngle=Math.max(maxZeroLimitAngle,R.length(R.qlog(R.qm(a.q[j],R.qinv(b.q[j])))));
  }
 }
}
assert(maxZeroLimitAngle<.0001,'discontinuity at zero inertia');console.log(JSON.stringify({cases,maxZeroLimitAngle,passed:'weight scales momentum, no inherited duplication, identical attraction, exact idle and continuous zero limit'}));
