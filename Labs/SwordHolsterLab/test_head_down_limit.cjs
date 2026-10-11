const assert=require('node:assert/strict'),H=require('./holster.js'),L=require('./headlook.js'),R=require('./recovery.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const {assertHeadBudget}=require('./head-test-helpers.cjs');
const ctx=L.make(data),radians=v=>v*Math.PI/180,down=(p,q)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.rotate(q,[1,0,0]),R.rotate(p[ctx.anchor].q,[1,0,0])))))*180/Math.PI;
assert.equal(H.sanitize({}).headMaxDownAngle,70);assert.equal(H.sanitize({headMaxDownAngle:-3}).headMaxDownAngle,0);assert.equal(H.sanitize({headMaxDownAngle:120}).headMaxDownAngle,90);
const reference=H.motion(data,'idle',0);let samples=0;
for(const pitch of [-40,0,45,70,89,90])for(const yaw of [-170,-90,0,90,170])for(const tilt of [0,45])for(const roll of [-80,0,80]){
 const p=reference.map(v=>({...v})),axis=R.qexp([0,radians(tilt),0]);p[ctx.anchor]={...p[ctx.anchor],q:axis};
 const q=R.qm(axis,R.qm(R.qexp([radians(yaw),0,0]),R.qm(R.qexp([0,0,radians(pitch)]),R.qexp([0,radians(roll),0])))),c=L.limitDown(ctx,p,q,70);
 assert(down(p,c)<=70+1e-7);assert(L.angle(c,L.limitDown(ctx,p,q.map(v=>-v),70))<1e-5,'quaternion sign independence');
 if(down(p,q)<=70)assert(L.angle(c,q)<1e-5,'already legal tilt unchanged');
 const twist=v=>{const a=R.qm(R.qinv(axis),v);return R.unit([a[0],0,0,a[3]]);};
 assert(L.angle(twist(q),twist(c))<1e-5,'vertical-axis twist/yaw preserved');
 assert.deepEqual(L.limitDown(ctx,p,q,90),q,'90 disables downward bound');samples++;
}
let cases=0,maxDown=-90,maxStep=0;
for(const motion of ['idle','walk'])for(const sheathe of [true,false])for(const gazeYaw of [-170,0,170]){
 const m=H.prepare(data,setup,{motion,sheathe,gazeYaw,headMaxDownAngle:70,duration:12});
 for(let tick=m.o.startTick+.37;tick<m.playbackDuration*60;tick+=.73){const f=H.sample(m,tick/60),a=down(f.pose,f.pose[ctx.head].q);maxDown=Math.max(maxDown,a);assert(a<=70+1e-6,`down cap ${motion} ${sheathe} ${gazeYaw} ${tick} ${a}`);const body=H.sampleBody(m,tick/60);for(let j=0;j<data.names.length;j++)if(!ctx.chain.includes(j))assert.deepEqual(f.pose[j],body.pose[j],'only neck/head authored');}
 for(let tick=m.o.startTick+1;tick<m.frames.length;tick++){assertHeadBudget(m,tick);maxStep=Math.max(maxStep,m.frames[tick].headLook.angularStep);}
 assert(m.completionTick!==null,'head returns and completes');cases++;
}
// If the spine moves the allowed region faster than the head's speed cap,
// apply only the minimum correction needed to remain inside the hard limit.
const curve=[[.2,.01],[.45,.05],[.65,.93],[.85,.99]];
const moving=H.prepare(data,setup,{motion:'walk',sheathe:false,headMaxDownAngle:70,maxHeadLookInVelocity:30,maxHeadLookOutVelocity:40,drawCurve:curve,drawSlideCurve:curve});
let forced=0;
for(let i=moving.o.startTick+1;i<moving.frames.length;i++){
 const f=moving.frames[i],previous=moving.frames[i-1].pose[ctx.head].q,bound=L.limitDown(ctx,f.pose,previous,70),minimum=L.angle(previous,bound),step=L.angle(previous,f.pose[ctx.head].q),cap=f.headLook.speedLimit/60;
 assert(step<=Math.max(cap,minimum)+.001,'no excess rotation beyond speed or moving-boundary correction');if(minimum>cap+.001)forced++;
}
const shifted=reference.map(v=>({...v})),previousQ=R.qexp([0,0,radians(70)]);shifted[ctx.anchor]={...shifted[ctx.anchor],q:R.qexp([0,0,radians(-10)])};
const previousState={q:previousQ,referenceQ:previousQ,worldDelta:[0,0,0],correction:[0,0,0]},bound=L.limitDown(ctx,shifted,previousQ,70);
const moved=L.step(ctx,shifted,reference,[0,0,0],previousState,{tick:1,startTick:0,lookOutTick:0,maxLookIn:.6,maxLookOut:.6,lookOutQ:previousQ,maxDownAngle:70});
assert(Math.abs(L.angle(previousQ,moved.state.q)-L.angle(previousQ,bound))<1e-6,'rapid spine movement applies minimum legal correction');
assert(down(shifted,moved.state.q)<=70+1e-7);
const fixture=require('./data/head-tilt-regression.json'),regression=H.prepare(data,setup,fixture.parameters),visible=H.sample(regression,fixture.time);
assert(down(visible.pose,visible.pose[ctx.head].q)<=30.00001,'reported sideways head at 30 now has at most 30 actual tilt');
for(let tick=regression.o.startTick+.19;tick<regression.completionTick;tick+=.41){const f=H.sample(regression,tick/60);assert(down(f.pose,f.pose[ctx.head].q)<=30.00001,'current setup throughout action');}
console.log(JSON.stringify({passed:true,projectionCases:samples,motionCases:cases,maxDown,maxStep}));
