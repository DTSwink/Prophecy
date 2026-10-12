const assert=require('node:assert/strict'),R=require('./recovery.js'),P=require('./elbowpole.js'),H=require('./holster.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const dist=(a,b)=>R.length(R.sub(a,b)),I=[0,0,0,1],arm=[0,1,2],spine=3,rad=Math.PI/180;
const poseFor=d=>[{p:[0,0,0],q:I},{p:R.add(R.mul(d,20),[-15,0,0]),q:I},{p:R.mul(d,40),q:I},{p:[0,0,0],q:I}];
let prior=null,first=null;
for(let degrees=0;degrees<=360;degrees+=2){
 const q=R.qexp([degrees*rad,0,0]),pose=poseFor(R.rotate(q,[0,1,0])),basis=P.frame(pose,arm,spine,prior);
 const angle=P.advance(55,55,0,1/60),out=P.apply(pose,arm,spine,angle,basis);
 assert(Math.abs(P.measure(out,arm,spine,basis)-55)<1e-9,'horizontal sweep retains preference with zero turning budget');
 if(!first)first=out;
 assert(dist(out[1].p,R.rotate(q,first[1].p))<1e-8,'elbow follows arm sweep around spine');
 assert.deepEqual(out[2],pose[2],'wrist pose untouched');
 assert(Math.abs(dist(out[0].p,out[1].p)-dist(pose[0].p,pose[1].p))<1e-8);
 assert(Math.abs(dist(out[2].p,out[1].p)-dist(pose[2].p,pose[1].p))<1e-8);
 const world=R.qexp([.4,.7,-.5]),move=[20,30,-2],moved=pose.map(v=>({p:R.add(move,R.rotate(world,v.p)),q:R.qm(world,v.q)}));
 const result=P.apply(moved,arm,spine,55,P.frame(moved,arm,spine,prior));
 assert(dist(result[1].p,R.add(move,R.rotate(world,out[1].p)))<1e-7,'torso/world rotation carries preference');prior=basis;
}
prior=null;let previousDirection=null,maxVerticalStep=0;
for(let degrees=-10;degrees<=10;degrees+=.1){
 const d=[Math.cos(degrees*rad),Math.sin(degrees*rad),0],pose=poseFor(d),basis=P.frame(pose,arm,spine,prior);
 if(previousDirection)maxVerticalStep=Math.max(maxVerticalStep,Math.acos(Math.min(1,R.dot(basis.zero,previousDirection)))/rad);
 assert(basis.zero.every(Number.isFinite)&&Math.abs(R.dot(basis.zero,d))<1e-8);previousDirection=basis.zero;prior=basis;
}
assert(maxVerticalStep<.11,'crossing vertical does not flip the frame');
assert.equal(P.target({clear:{pole:170},seated:{pole:-170}},.5),180,'endpoints interpolate across nearest angular wrap');
let cases=0,maxPreviewDifference=0,maxGripError=0,maxMeasuredSpeed=0;
for(const motion of ['idle','walk'])for(const sheathe of [true,false]){
 const targets=H.sanitize(saved).bodyTargets;targets.clear.pole=-40;targets.seated.pole=70;
 const m=H.prepare(data,setup,{...saved,motion,sheathe,duration:10,bodyTargets:targets,maxElbowPoleAngularSpeed:25,swordRelativeSlidePole:false,entryInertia:0});
 assert(m.plan.arrives&&m.completionTick!==null,'new pole settings complete');
 const keys=m.poleGuides.keys;
 for(let k=1;k<keys.length;k++)assert(Math.abs(keys[k].angle-keys[k-1].angle)<=25/240+1e-8,'angle cap uses playback time despite timing curves');
 for(const insertion of [0,.25,.5,.75,1]){
  const f=H.previewBody(m,insertion),play=H.sample(m,f.previewTime);
  for(let j=0;j<data.names.length;j++){maxPreviewDifference=Math.max(maxPreviewDifference,dist(f.pose[j].p,play.pose[j].p));assert.deepEqual(f.pose[j],play.pose[j],'settled preview is the actual playback pose including early return');}
 }
 for(let tick=m.plan.endTick;tick<m.plan.slideEnd;tick+=.37){const f=H.sample(m,tick/60);maxGripError=Math.max(maxGripError,f.handError);assert(f.handError<.6,'grip preserved through slide/early return');}
 let basis=null,angle=null;
 for(let k=m.o.startTick*8;k<=m.plan.slideEnd*8;k++){
  const f=H.sample(m,k/480);basis=P.frame(f.pose,m.arm,m.bodyContext.top,basis);const current=P.measure(f.pose,m.arm,m.bodyContext.top,basis);
  if(angle!==null){const speed=Math.abs(P.wrap(current-angle))*480;maxMeasuredSpeed=Math.max(maxMeasuredSpeed,speed);assert(speed<=25+1e-5,'rendered elbow preference obeys cap between guides, including early FK return');}angle=current;
 }
 const frozen=JSON.stringify(m.sourceFrames);for(let t=0;t<m.playbackDuration;t+=.071)H.sample(m,t);assert.equal(JSON.stringify(m.sourceFrames),frozen,'stateless playback');
 cases++;
}
console.log(JSON.stringify({passed:true,horizontalSamples:181,maxVerticalStep,cases,maxGripError,maxPreviewDifference,maxMeasuredSpeed}));
