const assert=require('node:assert/strict'),H=require('./holster'),R=require('./recovery'),Curve=require('./retime');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
let cases=0,minStart=Infinity,maxStart=-Infinity;
for(const noCheat of [false,true])for(const motion of ['idle','walk','run'])for(const linear of [false,true]){
 const o={...saved,...saved.sheatheBody,sheathe:true,noCheat,motion,duration:8,shrinkPercent:25,shrinkDuration:.5};
 if(linear)o.sheatheSlideCurve=Curve.linear();
 const m=H.prepare(data,setup,o),entry=m.sheathEntry,start=entry.tick,end=m.plan.slideEnd;
 minStart=Math.min(minStart,entry.insertion);maxStart=Math.max(maxStart,entry.insertion);
 assert(Math.abs(m.frames[start].insertion-entry.insertion)<1e-10);
 assert.equal(end-start,Math.max(1,Math.ceil(setup.bladeLength*.75*Math.abs(1-entry.insertion)/o.slidingSpeed*60)),'time covers only remaining slide');
 const curve=Curve.prepare(o.sheatheSlideCurve);
 for(let i=start;i<=end;i++){
  const expected=entry.insertion+(1-entry.insertion)*Curve.sample(curve,(i-start)/(end-start));
  assert(Math.abs(m.frames[i].insertion-expected)<1e-9);
 }
 const startPose=m.frames[start],align=require('./tipalign').sample(H,setup,m.tip,m.tipAlign,startPose.holster,start);
 assert(R.length(R.sub(startPose.sword.p,align.sword.p))<1e-8,'no sword shift at slide entry');
 assert(H.angle(startPose.sword.q,align.sword.q)<1e-5,'no sword rotation jump at slide entry');
 const fk=m.frames.find(f=>f.tick>start&&f.tick<=end&&f.insertion>=o.sheatheReturn.startFraction-1e-8);
 if(o.sheatheReturn.enabled)assert(Math.abs(m.fkReturn.start*60-fk.tick)<1e-8,'FK return uses actual insertion');
 const head=m.frames.find(f=>f.tick>start&&f.tick<=end&&f.insertion>=o.sheatheHeadLookOutThreshold-1e-8);
 assert.equal(m.frames[end].headLook.lookOutTick,head.tick,'head threshold uses actual insertion');
 assert(m.completionTick!==null);cases++;
}
console.log(JSON.stringify({cases,minStart,maxStart,remainingDistanceTiming:true,continuousSlideEntry:true,actualInsertionThresholds:true}));
