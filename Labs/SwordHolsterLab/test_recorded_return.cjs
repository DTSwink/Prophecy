const assert=require('node:assert/strict'),P=require('./sequence'),R=require('./recovery'),H=require('./holster'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const results=[];
for(const c of require('./diagnostics/problem-motions.json').filter(c=>c.clip.returnCapture)){
 data.motions[c.id]=c.clip;
 const o=c.parameters,m=P.prepare(data,setup,o),r=m.returnCapture;
 assert.equal(m.bladeLength,setup.bladeLength,'startup source information requires the actual blade length');
 const vertices=r.holsterMesh.sections.flatMap(s=>s.vertices),dimensions=[0,1,2].map(k=>Math.max(...vertices.map(v=>v[k]))-Math.min(...vertices.map(v=>v[k])));
 const reference=setup.holsterMesh.sections.flatMap(s=>s.vertices),expectedDimensions=[0,1,2].map(k=>(Math.max(...reference.map(v=>v[k]))-Math.min(...reference.map(v=>v[k])))*setup.holster.s[k]);
 dimensions.forEach((v,k)=>assert(Math.abs(v-expectedDimensions[k])<.001,'captured baked geometry must retain holster dimensions'));
 const grip=r.frames.find(f=>f.phase==='Slide'&&f.insertion>=.999999),seated=H.compose(r.seatedSword,grip.holster),held=H.compose(H.scaledGrip(setup,grip.scale),grip.pose[m.arm[2]]);
 assert(R.length(R.sub(seated.p,held.p))<1e-8,'captured seated sword must match actual grip, including changed mesh pivot');
 assert.equal(typeof m.o.drawReturn.elbowIKCorrection,'boolean');
 for(const t of [.01,.26,.5,.83]){const f=P.sample(m,t);assert(f.pose.every(b=>[...b.p,...b.q].every(Number.isFinite)));assert.deepEqual(P.sample(m,t),f);}
 const hand=m.arm[2],root=data.names.indexOf('root'),off=P.retime(m,{...o,drawReturn:{...o.drawReturn,swordPointSpeed:0}});
 // The exported bodyPose precedes HandAxisStep: rebuild that stage, never
 // treat its hand quaternion as the final captured sword rotation.
 for(const speed of [-180,180])for(const exponent of [1,1.5])for(const cutoff of [.25,.5]){
  const on=P.retime(off,{...off.o,drawReturn:{...off.o.drawReturn,swordPointSpeed:speed,swordPointExponent:exponent,swordPointCutoff:cutoff}});
  assert(on.swordPoint,'recorded returns must run the normal sword arc');
  const duration=on.armReturn.timing.duration,window=duration*cutoff,entry=on.frames[r.release].pose;
  const start=R.qm(R.qinv(entry[root].q),entry[hand].q);
  for(let i=0;i<on.frames.length;i++){
   const a=off.frames[i],b=on.frames[i];
   for(let j=0;j<data.names.length;j++){
    assert.deepEqual(a.pose[j].p,b.pose[j].p,'arc must not change elbow/hand positions');
    if(j!==hand)assert.deepEqual(a.pose[j],b.pose[j],'arc only changes the hand rotation');
   }
   if(i<=r.release)assert.deepEqual(a.pose,b.pose,'lead-in and grip unchanged');
   const elapsed=(i-r.release)/60;
   if(elapsed>0&&elapsed<=window){
    const u=elapsed/window,p=exponent===1?u:Math.pow(u,exponent)/(Math.pow(u,exponent)+Math.pow(1-u,exponent))/exponent;
    const expected=R.qm(b.pose[root].q,R.qm(start,R.qexp([speed*Math.PI/180*window*p,0,0])));
    assert(H.angle(b.pose[hand].q,expected)<1e-5,'signed local-axis speed and sigmoid budget');
   }
   if(elapsed>=duration)assert(H.angle(a.pose[hand].q,b.pose[hand].q)<1e-5,'existing return resumes completely');
  }
  const at=r.release/60+window;
  assert(H.angle(P.sample(on,at-1e-7).pose[hand].q,P.sample(on,at+1e-7).pose[hand].q)<.001,'continuous cutoff');
  const t=r.release/60+.07,f=P.sample(on,t);
  assert(H.angle(f.sword.q,H.compose(H.scaledGrip(setup,f.scale),f.pose[hand]).q)<1e-5,'fractional sword follows authored hand');
  assert.deepEqual(P.sample(on,t),f,'scrubbing is deterministic');
  assert.deepEqual(P.retime(on,off.o).frames,off.frames,'zero speed restores the exact underlying return');
 }
 results.push({id:c.id,frames:m.frames.length,firstTick:r.firstTick,release:r.firstTick+r.release});
}
console.log(JSON.stringify({passed:true,results}));
