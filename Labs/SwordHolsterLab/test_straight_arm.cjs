// Captured live slide-entry regression: old projection introduced 125deg twist.
const assert=require('node:assert/strict'),H=require('./holster.js'),P=require('./elbowpole.js'),R=require('./recovery.js'),fixture=require('./data/straight-arm-regression.json');
let peak=0;
for(const c of fixture.cases){
 const pose=structuredClone(c.input);H.solve(pose,fixture.arm,c.goal);
 const out=P.apply(pose,fixture.arm,4,c.angle,P.frame(pose,fixture.arm,4,c.basis));
 for(const k of fixture.arm){const step=H.angle(c.before[k].q,out[k].q);peak=Math.max(peak,step);assert(step<15,`Unexpected arm roll ${step}`);}
 assert(R.length(R.sub(out[3].p,c.goal.p))<1e-8);
 for(const [a,b] of [[1,2],[2,3]])assert(Math.abs(R.length(R.sub(out[b].p,out[a].p))-R.length(R.sub(c.input[b].p,c.input[a].p)))<1e-8);
}
console.log({cases:fixture.cases.length,peakDegrees:peak});
