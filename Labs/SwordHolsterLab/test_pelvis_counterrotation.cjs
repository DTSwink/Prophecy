const assert=require('node:assert/strict'),fs=require('node:fs'),B=require('./bodyreach.js'),H=require('./holster.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const entry=H.motion(data,'run',70/60),ctx=B.make(data,H.motion(data,'idle',0),entry),target=B.target(ctx,B.sanitize(saved.bodyTargets),.4),origin=entry[ctx.pelvis].p;
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI;
const held=B.apply(ctx,entry,target);
let maxRotationError=0,maxTranslationError=0;
for(let i=0;i<361;i++){
 const t=i/180,q=R.qm(R.qexp([.9*Math.sin(t*4),0,0]),R.qm(R.qexp([0,.6*Math.sin(t*3),0]),R.qexp([0,0,t*1.1])));
 const base=entry.map(v=>({...v,p:R.add(origin,R.rotate(q,R.sub(v.p,origin))),q:R.qm(q,v.q)})),out=B.apply(ctx,base,target);
 const expected=R.qm(ctx.entryPelvisQ,target.slice(0,4));maxRotationError=Math.max(maxRotationError,angle(out[ctx.top].q,expected));
 assert(angle(out[ctx.top].q,expected)<1e-8,'pelvis yaw/pitch/roll cannot rotate spine05');
 assert(angle(out[ctx.clav].q,R.qm(expected,target.slice(4,8)))<1e-8,'right clavicle follows corrected spine');
 for(const j of ctx.affected)assert(R.length(R.sub(out[j].p,held[j].p))<1e-8,'pelvis rotation cannot sway the upper body position');
 const shift=[t*33,Math.sin(t)*41,t*12],translated=base.map(v=>({...v,p:R.add(v.p,shift)})),moved=B.apply(ctx,translated,target);
 for(let j=0;j<out.length;j++){const error=R.length(R.sub(moved[j].p,R.add(out[j].p,shift)));maxTranslationError=Math.max(maxTranslationError,error);assert(error<1e-8,'translation is retained');assert(angle(moved[j].q,out[j].q)<1e-8);}
 for(const j of ctx.affected){const p=ctx.parents[j];assert(Math.abs(R.length(R.sub(out[j].p,out[p].p))-R.length(R.sub(entry[j].p,entry[p].p)))<1e-8,'bone lengths retained');}
}
// Partial compensation rotates the entire held chain rigidly about the live pelvis.
for(const amount of [0,.25,.5,.75,1])for(let i=0;i<41;i++){
 const q=R.qexp([.6*Math.sin(i),.4*Math.cos(i),i*.04]);
 const base=entry.map(v=>({...v,p:R.add(origin,R.rotate(q,R.sub(v.p,origin))),q:R.qm(q,v.q)}));
 const partial=B.make(data,H.motion(data,'idle',0),entry,amount),out=B.apply(partial,base,target);
 const frame=R.qslerp(base[ctx.pelvis].q,ctx.entryPelvisQ,amount),delta=R.qm(frame,R.qinv(ctx.entryPelvisQ));
 for(const j of ctx.affected){
  assert(R.length(R.sub(out[j].p,R.add(origin,R.rotate(delta,R.sub(held[j].p,origin)))))<1e-8,'partial compensation carries the whole chain coherently');
  assert(angle(out[j].q,R.qm(delta,held[j].q))<1e-8);
 }
}
assert.equal(H.sanitize({}).pelvisRotationCompensation,1);
assert.equal(H.sanitize({pelvisRotationCompensation:-2}).pelvisRotationCompensation,0);
assert.equal(H.sanitize({pelvisRotationCompensation:2}).pelvisRotationCompensation,1);
let cases=0;
for(const amount of [0,.5,1])for(const motion of ['walk','run'])for(const sheathe of [false,true]){
 const action=sheathe?'sheathe':'draw',o={...saved,pelvisRotationCompensation:amount,motion,sheathe,startTick:70,entryInertia:0,[action+'Return']:{enabled:false}},m=H.prepare(data,setup,o);
 assert(m.plan.arrives,'D/S completes');const end=m.plan.slideEnd;
 const samples=[];
 for(let tick=70;tick<end;tick+=.37){
  const f=H.sampleBody(m,tick/60);assert(angle(f.pose[m.bodyContext.top].q,R.qm(R.qslerp(f.pose[m.pelvis].q,m.bodyContext.entryPelvisQ,amount),f.body.applied.slice(0,4)))<1e-7,'fractional playback cancels pelvis rotation');samples.push([tick,f.pose]);
 }
 for(const [tick,pose] of samples.reverse())assert.deepEqual(H.sampleBody(m,tick/60).pose,pose,'scrubbing does not accumulate compensation');
 cases++;
}
const result={passed:true,rotationSamples:361,cases,maxRotationErrorDegrees:maxRotationError,maxTranslationErrorCm:maxTranslationError};
fs.writeFileSync('Saved/Diagnostics/SwordPelvisCounterrotation20261012/verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
