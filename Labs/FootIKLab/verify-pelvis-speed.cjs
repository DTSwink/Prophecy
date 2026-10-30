const fs=require('fs'),crypto=require('crypto'),assert=require('assert/strict');
const F=require('./surface.js'),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),{load}=require('./test-bank.cjs');
const checks=[],check=(name,value)=>{assert(value,name);checks.push(name);};
const normal=angle=>[0,Math.cos(angle*Math.PI/180),-Math.sin(angle*Math.PI/180)];
const input={minGravityIncline:80,pelvisCloser:10,pelvisCloserMax:30,pelvisSpeedMin:1,pelvisSpeedMax:5};
for(const angle of [0,80,85,90])for(const speed of [0,1,2,3,5,9]){
 const expected=(.1+.2*Math.max(0,Math.min(1,(speed-1)/4)))*Math.max(0,(angle-80)/10);
 check(`speed / angle ${speed} / ${angle}`,Math.abs(F.pelvisCloser(normal(angle),K.sanitize(input),[0,0,speed])-expected)<1e-12);
}
check('Falling and lateral components count toward total speed',Math.abs(F.pelvisCloser(normal(90),K.sanitize(input),[0,-3,4])-.3)<1e-12);
check('High speed can reduce rather than increase offset',Math.abs(F.pelvisCloser(normal(90),K.sanitize({...input,pelvisCloser:30,pelvisCloserMax:10}),[0,0,3])-.2)<1e-12);
const migrated=K.sanitize({pelvisCloser:10});
check('Old tuning migrates to equal endpoints',migrated.pelvisCloser===10&&migrated.pelvisCloserMax===10&&migrated.pelvisSpeedMin===0&&migrated.pelvisSpeedMax===3.5);
check('Migration persists idempotently',JSON.stringify(K.sanitize(migrated))===JSON.stringify(migrated));
const equal=K.sanitize({...input,pelvisSpeedMin:5,pelvisSpeedMax:1});
check('Reversed range clamps and equal thresholds stay finite',equal.pelvisSpeedMax===5&&F.pelvisCloser(normal(90),equal,[0,0,5])===.1&&F.pelvisCloser(normal(90),equal,[0,0,6])===.3);
check('Malformed speed values have safe defaults',K.sanitize({pelvisSpeedMin:'bad',pelvisSpeedMax:Infinity}).pelvisSpeedMax===3.5);
check('Disabled IK and minimum90 have no shift',F.pelvisCloser(normal(90),K.sanitize({...input,enabled:false}),[0,0,3])===0&&F.pelvisCloser(normal(90),K.sanitize({...input,minGravityIncline:90}),[0,0,3])===0);
// Complete frame hashes captured from the accepted angle-only version, before this edit.
const approved={walk:'10e8a12080c531bcbde9ec6783c4996c255fc9a96f69977cde15d3db3846d0aa',run:'285a7671743fa8a41f58008ff4345f99db4b782650ae1ec6aacdb98160c38f55'};
const cases=[];
for(const gait of ['walk','run']){
 const run=load(gait,.21),base={gait,slopeAngle:90,minGravityIncline:80,pelvisCloser:10};
 const after=F.prepare(run,base);
 check(`${gait}: migrated saved scene exactly matches angle-only motion`,crypto.createHash('sha256').update(JSON.stringify(after.frames)).digest('hex')===approved[gait]);
 const model=F.prepare(run,{...base,...input});let error=0,minHinge=1,boneError=0;
 for(const f of model.frames){
  const n=R.rotate(f.surface.gaitRotation,[0,1,0]),expected=R.mul(n,-F.pelvisCloser(n,model.settings,f.surface.velocity));
  error=Math.max(error,R.length(R.sub(R.sub(f.pose.points[1],f.raw.points[1]),expected)));
  for(let j=2;j<run.names.length;j++)boneError=Math.max(boneError,Math.abs(R.length(R.sub(f.pose.points[j],f.pose.points[run.parents[j]]))-R.length(R.sub(f.raw.points[j],f.raw.points[run.parents[j]]))));
  for(const side of ['L','R']){const l=S.leg(f.raw,run.names,side),v=R.sub(l.upperAxis,R.mul(R.unit(R.sub(f.raw.points[l.foot],f.raw.points[l.hip])),R.dot(l.upperAxis,R.unit(R.sub(f.raw.points[l.foot],f.raw.points[l.hip])))));if(R.length(v)>.15)minHinge=Math.min(minHinge,R.dot(l.normal,S.leg(f.pose,run.names,side).normal));}
 }
 check(`${gait}: measured speed drives exact surface-normal shift`,error<1e-8);
 check(`${gait}: bones, knees, pin and sole constraints retained`,boneError<1e-8&&minHinge>0&&model.metrics.maxContactDrift<1e-8&&model.metrics.maxPenetration<1e-5&&model.metrics.maxReachError<1e-6);
 cases.push({gait,error,boneError,minHinge,metrics:model.metrics});
}
fs.writeFileSync('snapshots/pelvis-speed-verification.json',JSON.stringify({passed:true,checks,cases},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,cases}));
