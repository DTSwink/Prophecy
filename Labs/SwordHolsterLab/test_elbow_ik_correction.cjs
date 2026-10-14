const assert=require('node:assert/strict'),fs=require('fs'),F=require('./fkreturn'),R=require('./recovery'),H=require('./holster');
const cases=process.argv[2]?JSON.parse(fs.readFileSync(process.argv[2],'utf8')):[...require('./diagnostics/elbow-return-regressions.json'),...require('./diagnostics/elbow-ik-return-regressions.json')];
let maxShift=0,maxOrientationError=0,maxBoneError=0,nearEnd=0;const report=[];
for(const c of cases){
 const inputs=value=>({...c.input,profile:{...c.input.profile,elbowIKCorrection:value}}),trial=F.prepare(inputs(true)),old=F.prepare(inputs(false)),raw=F.prepare({...c.input,profile:{...c.input.profile,elbowIKCorrection:false}});
 const arm=['upperarm_r','lowerarm_r','hand_r'].map(n=>c.input.names.indexOf(n)),rows=[];let previous;
 for(const frame of c.frames){const elapsed=(frame.tick-c.release)/60,p=F.sample(trial,frame.base,elapsed),u=F.sample(raw,frame.base,elapsed),o=F.sample(old,frame.base,elapsed);
  assert(p.every(t=>[...t.p,...t.q].every(Number.isFinite)));
  const shift=R.sub(p[arm[2]].p,u[arm[2]].p),wristError=R.length(shift),axis=R.sub(u[arm[2]].p,u[arm[0]].p);
  // The soft zone may change radial reach, never shove the wrist sideways.
  assert(R.length(R.cross(shift,R.unit(axis)))<1e-8,'sideways wrist displacement');
  maxShift=Math.max(maxShift,wristError);maxOrientationError=Math.max(maxOrientationError,H.angle(p[arm[2]].q,u[arm[2]].q));
  assert(H.angle(p[arm[2]].q,u[arm[2]].q)<1e-4);
  for(let k=1;k<3;k++){const err=Math.abs(R.length(R.sub(p[arm[k]].p,p[arm[k-1]].p))-R.length(R.sub(u[arm[k]].p,u[arm[k-1]].p)));maxBoneError=Math.max(maxBoneError,err);assert(err<1e-8);}
  if(elapsed>trial.timing.duration-1/60&&elapsed<trial.timing.duration)nearEnd=Math.max(nearEnd,R.length(R.sub(p[arm[1]].p,u[arm[1]].p)));
  rows.push({tick:frame.tick,shift:wristError,oldShift:R.length(R.sub(o[arm[2]].p,u[arm[2]].p)),step:previous?R.length(R.sub(p[arm[2]].p,previous[arm[2]].p)):0});previous=p;
 }
 // Reverse sampling must not alter the trial and its release/end are exact.
 const ret=F.prepare(inputs(true));for(const frame of [...c.frames].reverse())assert.deepEqual(F.sample(ret,frame.base,(frame.tick-c.release)/60),F.sample(trial,frame.base,(frame.tick-c.release)/60));
 assert.deepEqual(F.sample(trial,c.input.base,trial.timing.duration),c.input.base);
 report.push({name:c.name,release:c.release,rows});
}
assert(maxShift<.25,'soft-zone wrist adjustment unexpectedly large');
assert(nearEnd<.01,'constraint must release continuously into the resting pose');
console.log(JSON.stringify({passed:true,cases:cases.length,maxShift,maxOrientationError,maxBoneError,nearEnd,reported:report.filter(c=>[658,1137].includes(c.release)&&c.name.endsWith('_0')).map(c=>({...c,rows:c.rows.slice(0,4)}))}));
