const assert=require('node:assert/strict'),fs=require('node:fs');
const H=require('./holster.js'),R=require('./recovery.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const state=JSON.parse(fs.readFileSync(__dirname+'/state.json')),results=[];
for(const motion of ['walk','run']){
 const c=data.motions[motion];assert.equal(c.fps,60);assert.equal(c.recording.warmupTicks,180);
 if(motion==='walk'){assert.equal(c.recording.checkpoint,'run');assert.equal(c.recording.movementInputLength,.4);assert.equal(c.recording.speedScale,1);}
 assert(c.duration>=10&&c.duration<=12);assert(c.recording.loopSeamCm<.2&&c.recording.loopSeamDegrees<1);
 assert.equal(H.sanitize({motion}).motion,motion);
 for(let t=0;t<c.duration*2;t+=.031){const p=H.motion(data,motion,t);assert(p.every(b=>[...b.p,...b.q].every(Number.isFinite)));}
 for(let i=0;i<c.frames.length-1;i+=11){
  const p=H.motion(data,motion,i/60);
  for(let j=0;j<p.length;j++)assert(R.length(R.sub(p[j].p,c.frames[i][j].slice(0,3)))<1e-8,'preserves recorded tick positions');
 }
 for(const sheathe of [true,false]){
  const options={...state.parameters,motion,sheathe};
  if(state.controls?.bypassCurves)for(const k of ['drawCurve','drawSlideCurve','sheatheCurve','sheatheSlideCurve'])options[k]=[[.2,.2],[.4,.4],[.6,.6],[.8,.8]];
  const m=H.prepare(data,setup,options);let maxGrip=0;
  for(let t=0;t<m.playbackDuration;t+=.013){const f=H.sample(m,t),base=H.motion(data,motion,t,options.gazeYaw);
   assert(f.pose.every(b=>[...b.p,...b.q].every(Number.isFinite)));
   assert(R.length(R.sub(f.pose[1].p,base[1].p))<1e-7,'gait retains independent clock');
   if(f.phase==='Slide')maxGrip=Math.max(maxGrip,f.handError);
  }
  assert.equal(H.sample(m,m.playbackDuration).phase,sheathe?'Holstered':'Held','D/S completes with new base motion');
  assert(maxGrip<.2,'fractional sliding grip error');
  results.push({motion,sheathe,completionTick:m.completionTick,lastPhase:H.sample(m,m.playbackDuration).phase,maxGrip});
 }
}
console.log(JSON.stringify(results,null,2));
