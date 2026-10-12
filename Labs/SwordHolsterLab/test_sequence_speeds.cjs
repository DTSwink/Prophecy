const assert=require('node:assert/strict'),P=require('./sequence.js'),H=require('./holster.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const speeds=['maxReachSpeed','maxReachRotationSpeed','slidingSpeed'];
const draw={maxReachSpeed:300,maxReachRotationSpeed:9000,slidingSpeed:250};
const sheathe={maxReachSpeed:230,maxReachRotationSpeed:600,slidingSpeed:150};
for(const motion of ['idle','walk','run'])for(const startsS of [true,false]){
 const o={...saved,motion,sequenceMode:true,duration:12,sheathe:startsS,...(startsS?sheathe:draw),
  drawBody:{...saved.drawBody,...draw},sheatheBody:{...saved.sheatheBody,...sheathe}};
 const model=P.prepare(data,setup,o),{first,second,offset}=model.sequence;
 assert(second&&second.completionTick!==null,'sequence finishes');
 for(const [part,values,sheathe,delay] of [[first,startsS?o.sheatheBody:o.drawBody,startsS,0],[second,startsS?o.drawBody:o.sheatheBody,!startsS,offset]]){
  const single=H.prepare(data,setup,{...o,...values,sheathe,startTick:delay===0?o.startTick:0},delay);
  assert.deepEqual(part.frames,single.frames,'sequence motion and timing equal the independently configured action');
  for(const k of speeds)assert.equal(part.o[k],values[k]);
  assert.deepEqual(part.fkReturn.options,part.o[sheathe?'sheatheReturn':'drawReturn']);
 }
 const retimed=P.retime(model,o);
 assert.deepEqual(retimed.frames,model.frames,'retiming from the other action keeps both speeds');
 assert.equal(retimed.sequence.second.sourceFrames,second.sourceFrames,'unchanged plan reused');
 const secondKey=startsS?'drawBody':'sheatheBody';
 const slower=P.prepare(data,setup,{...o,[secondKey]:{...o[secondKey],slidingSpeed:80}});
 assert.deepEqual(slower.sequence.first.frames,first.frames,'second speed edit leaves first motion unchanged');
 assert(slower.sequence.second.plan.slideEnd-slower.sequence.second.plan.endTick>second.plan.slideEnd-second.plan.endTick,'second speed changes its actual slide duration');
}
console.log('PASS: idle/walk/run independent S/D motion and timing, action selection, retiming, FK profiles and D speed changes');
