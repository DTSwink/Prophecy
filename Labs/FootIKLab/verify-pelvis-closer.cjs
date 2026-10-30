const fs=require('fs'),cp=require('child_process'),Module=require('module'),assert=require('assert/strict');
const F=require('./surface.js'),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),{load}=require('./test-bank.cjs');
const checks=[],cases=[],check=(name,ok)=>{assert(ok,name);checks.push(name);};
const normal=deg=>[0,Math.cos(deg*Math.PI/180),-Math.sin(deg*Math.PI/180)];
for(const minimum of [0,45,80,89])for(const angle of [0,minimum,(minimum+90)/2,90]){
 const actual=F.pelvisCloser(normal(angle),K.sanitize({minGravityIncline:minimum,pelvisCloser:20})),expected=angle<=minimum?0:.2*(angle-minimum)/(90-minimum);
 check(`ramp ${minimum}/${angle}`,Math.abs(actual-expected)<1e-12);
}
check('Minimum90 and disabled IK have no offset',F.pelvisCloser(normal(90),K.sanitize({minGravityIncline:90}))===0&&F.pelvisCloser(normal(90),K.sanitize({enabled:false}))===0);
// Compare against the exact user-approved push, without changing the checkout.
const oldPath=require.resolve('./surface.js'),old=new Module(oldPath,module);old.filename=oldPath;old.paths=module.paths;
old._compile(cp.execFileSync('git',['show','16d1fe0a:Labs/FootIKLab/surface.js'],{encoding:'utf8'}),oldPath);
for(const gait of ['walk','run']){
 const run=load(gait,.21);
 for(const slopeAngle of [0,80,85,90]){
  const input={gait,slopeAngle,minGravityIncline:80,pelvisCloser:0},before=old.exports.prepare(run,input),off=F.prepare(run,input);
  check(gait+'/'+slopeAngle+' zero matches approved motion exactly',JSON.stringify(before.frames)===JSON.stringify(off.frames));
  for(const pelvisCloser of [20,50]){
   const m=F.prepare(run,{...input,pelvisCloser});let offsetError=0,boneError=0,minHinge=1,upperRotation=0;
   for(let i=0;i<m.frames.length;i++){const f=m.frames[i],p=run.names.indexOf('pelvis'),n=R.rotate(f.surface.gaitRotation,[0,1,0]),expected=R.mul(n,-F.pelvisCloser(n,m.settings));
    offsetError=Math.max(offsetError,R.length(R.sub(R.sub(f.pose.points[p],f.raw.points[p]),expected)));
    for(let j=2;j<run.names.length;j++)boneError=Math.max(boneError,Math.abs(R.length(R.sub(f.pose.points[j],f.pose.points[run.parents[j]]))-R.length(R.sub(f.raw.points[j],f.raw.points[run.parents[j]]))));
    for(let j=1;j<run.names.length;j++)if(!/^(thigh|calf|foot|ball)_/.test(run.names[j]))upperRotation=Math.max(upperRotation,R.length(R.qlog(R.qm(f.pose.q[j],R.qinv(f.raw.q[j])))));
    for(const side of ['L','R']){const l=S.leg(f.raw,run.names,side),v=R.sub(l.upperAxis,R.mul(R.unit(R.sub(f.raw.points[l.foot],f.raw.points[l.hip])),R.dot(l.upperAxis,R.unit(R.sub(f.raw.points[l.foot],f.raw.points[l.hip])))));if(R.length(v)>.15)minHinge=Math.min(minHinge,R.dot(l.normal,S.leg(f.pose,run.names,side).normal));}
   }
   const label=gait+'/'+slopeAngle+'/'+pelvisCloser;
   check(label+' exact normal offset and unchanged upper rotation',offsetError<1e-8&&upperRotation<1e-8);
   check(label+' bones and signed hinge retained',boneError<1e-8&&minHinge>0);
   check(label+' contacts and shoe clearance retained',m.metrics.maxContactDrift<1e-8&&m.metrics.maxPenetration<1e-5&&m.metrics.maxReachError<1e-6);
   if(slopeAngle<=80)check(label+' below minimum matches accepted motion',JSON.stringify(m.frames)===JSON.stringify(off.frames));
   cases.push({gait,slopeAngle,pelvisCloser,offsetError,boneError,minHinge,maxPinDrift:m.metrics.maxContactDrift,maxPenetration:m.metrics.maxPenetration,maxKneeStep:m.metrics.maxKneeStep});
  }
 }
}
fs.writeFileSync('snapshots/pelvis-closer-verification.json',JSON.stringify({passed:true,checks,cases},null,2));console.log(JSON.stringify({passed:true,checks:checks.length,cases}));
