const assert=require('node:assert/strict'),H=require('./holster'),Curve=require('./retime');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
let cases=0;
for(const noCheat of [false,true])for(const motion of ['idle','walk','run'])for(const shrinkDuration of [2.5,.25,.025])for(const linear of [false,true]){
 const o={...saved,...saved.sheatheBody,sheathe:true,noCheat,motion,shrinkPercent:25,shrinkDuration,duration:8};
 if(linear)o.sheatheCurve=Curve.linear();
 const m=H.prepare(data,setup,o),dock=m.tipAlign;
 assert(dock&&m.completionTick!==null,'action completes');
 for(let i=0;i<=dock.tick;i++){
  const expected=1-.25*Math.min(1,Math.max(0,i-o.startTick)/60/shrinkDuration);
  assert(Math.abs(m.frames[i].scale-expected)<1e-10,'normal-time shrink clock in both planners');
 }
 for(let i=dock.tick;i<=m.plan.endTick;i++)assert.equal(m.frames[i].scale,dock.scale,'attachment freezes scale');
 assert(Math.abs(m.frames[m.plan.slideEnd].scale-.75)<1e-10,'fully shrunk at slide completion');
 cases++;
}
for(const noCheat of [false,true]){
 const draws=[2.5,.025].map(shrinkDuration=>H.prepare(data,setup,{...saved,...saved.drawBody,sheathe:false,noCheat,motion:'run',shrinkDuration,duration:8}).frames);
 assert.deepEqual(draws[0],draws[1],'drawing unshrink is independent');
}
console.log(JSON.stringify({cases,normalClock:true,attachmentFreeze:true,drawingUnchanged:true}));
