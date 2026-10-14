const assert=require('node:assert/strict'),F=require('./fkreturn'),R=require('./recovery'),H=require('./holster'),P=require('./sequence');
const fixtures=[...require('./diagnostics/elbow-return-regressions.json'),...require('./diagnostics/elbow-ik-return-regressions.json')];
let samples=0,maxPosition=0,maxAngle=0;
for(const c of fixtures)for(const worldInertia of [false,true]){
 const input={...c.input,profile:{...c.input.profile,springReturn:false,worldInertia,inertia:0}},zero=F.prepare(input);
 for(const inertia of [1e-9,1e-6,.001,.1,.5,1]){
  const ret=F.prepare({...input,profile:{...input.profile,inertia}});
  assert.equal(ret.timing.duration,zero.timing.duration,'strength must not change duration');
  for(const f of c.frames){
   const t=(f.tick-c.release)/60,a=F.sample(zero,f.base,t),b=F.sample(ret,f.base,t);
   assert(b.every(j=>[...j.p,...j.q].every(Number.isFinite)));
   if(inertia<=1e-6)for(let j=0;j<a.length;j++){
    const p=R.length(R.sub(a[j].p,b[j].p)),q=H.angle(a[j].q,b[j].q);maxPosition=Math.max(maxPosition,p);maxAngle=Math.max(maxAngle,q);
    assert(p<.002&&q<.002,'tiny strength must approach the zero-inertia pose');
   }
   samples++;
  }
  assert.deepEqual(F.sample(ret,input.base,ret.timing.duration),input.base,'same exact return endpoint');
 }
}
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),c=require('./diagnostics/problem-motions.json').find(c=>c.id==='problem_4');data.motions[c.id]=c.clip;
const models=[0,.001,1].map(inertia=>P.prepare(data,setup,{...c.parameters,drawReturn:{...c.parameters.drawReturn,inertia}}));
assert(models.every(m=>m.completionTick===models[0].completionTick&&m.armReturn.timing.duration===models[0].armReturn.timing.duration));
const bend=m=>{
 const b=m.arm[1],h=m.arm[2],local=f=>R.localize(f.pose.map(t=>t.p),f.pose.map(t=>t.q),m.parents),start=local(m.frames[m.returnCapture.release]),next=local(m.frames[m.returnCapture.release+1]);
 const u0=R.unit(start.p[b]),axis=R.unit(R.cross(u0,R.rotate(start.q[b],R.unit(start.p[h])))),u=R.unit(next.p[b]),v=R.rotate(next.q[b],R.unit(next.p[h])),a=R.rotate(R.fromTo(u0,u),axis);
 return Math.atan2(R.dot(R.cross(u,v),a),R.dot(u,v))*180/Math.PI;
};
const bends=models.map(bend);assert(bends[0]>0&&bends[1]>0&&Math.abs(bends[1]-bends[0])<.1,'reported tiny-inertia elbow reversal');
console.log(JSON.stringify({passed:true,samples,maxPosition,maxAngle,reportedBends:bends,duration:models[0].armReturn.timing.duration}));
