const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const R=require('./recovery.js'),FK=require('./armfk.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const context=vm.createContext({module:{exports:{}},require:require('node:module').createRequire(__filename)});
vm.runInContext(fs.readFileSync(__dirname+'/holster.js','utf8').replace('function solve(pose,idx,goal){','function solve(pose,idx,goal){globalThis.endpointCalls=(globalThis.endpointCalls||0)+1;'),context);
const H=context.module.exports,dist=(a,b)=>R.length(R.sub(a,b)),reports=[];
for(const motion of ['idle','walk'])for(const sheathe of [true,false]){
 context.endpointCalls=0;
 const m=H.prepare(data,setup,{motion,sheathe,duration:8}),p=m.plan;
 assert(m.completionTick!==null,'action completes');assert.equal(context.endpointCalls,p.endpointSolves);
 assert(p.endpointSolves<(m.completionTick-m.o.startTick)/2,'only guide poses solved');
 let maxSlideError=0,maxSpeed=0,maxAngular=0;
 for(let tick=m.o.startTick;tick<=p.endTick;tick++){
  const f=m.frames[tick],actual=FK.capture(f.pose,m.arm,m.parents),expected=FK.blend(p.source,p.destination,FK.ease((tick-p.startTick)/(p.endTick-p.startTick)));
  for(let j=0;j<3;j++)assert(H.angle(actual[j].q,expected[j].q)<1e-5,'parent-local quaternion interpolation');
  if(tick>m.o.startTick){
   const previous=m.frames[tick-1],parent=m.parents[m.arm[0]];
   const hand=frame=>({p:R.rotate(R.qinv(frame.pose[parent].q),R.sub(frame.pose[m.arm[2]].p,frame.pose[m.arm[0]].p)),q:R.qm(R.qinv(frame.pose[parent].q),frame.pose[m.arm[2]].q)});
   const a=hand(previous),b=hand(f);maxSpeed=Math.max(maxSpeed,dist(a.p,b.p)*60);maxAngular=Math.max(maxAngular,H.angle(a.q,b.q)*60);
  }
 }
 assert(maxSpeed<=m.o.maxReachSpeed+.1);assert(maxAngular<=m.o.maxReachRotationSpeed+.1);
 for(const f of m.frames.filter(f=>f.phase==='Slide'))maxSlideError=Math.max(maxSlideError,f.handError);
 assert(maxSlideError<1,'FK slide stays within 1 cm of grip');
 const calls=context.endpointCalls;
 for(let t=.123;t<m.playbackDuration;t+=.071){
  const f=H.sample(m,t),i=Math.floor(t*60),u=t*60-i;
  for(const j of m.arm.slice(1)){
   const parent=m.parents[j],a=m.frames[i].pose,b=m.frames[Math.min(i+1,m.frames.length-1)].pose;
   let expectedLength=dist(a[j].p,a[parent].p)*(1-u)+dist(b[j].p,b[parent].p)*u;
   if(f.fkReturn){
    const base=H.motion(data,motion,t);
    expectedLength=m.fkReturn.model.upper[j]&&f.fkReturn.active?R.length(m.fkReturn.model.locals.at(-1).p[j]):dist(base[j].p,base[parent].p);
   }
   assert(Math.abs(dist(f.pose[j].p,f.pose[parent].p)-expectedLength)<1e-7,'subframe FK keeps bone lengths');
  }
 }
 assert.equal(context.endpointCalls,calls,'sampling never runs IK');
 if(!sheathe){
  const a=FK.capture(m.frames[p.slideEnd].pose,m.arm,m.parents),b=p.keys.at(-1).local;
  for(let j=0;j<3;j++)assert(H.angle(a[j].q,b[j].q)<1e-5,'no snap entering unshrink return');
 }
 reports.push({motion,sheathe,guideSolves:calls,reachEnd:p.endTick,completion:m.completionTick,maxSlideErrorCm:maxSlideError,maxReachCmPerSecond:maxSpeed,maxReachDegreesPerSecond:maxAngular});
}
console.log(JSON.stringify({passed:true,reports},null,2));
