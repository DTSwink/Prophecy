const assert=require('node:assert/strict'),H=require('./holster.js'),P=require('./elbowpole.js'),T=require('./retime.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
let cases=0,maxScheduleError=0,maxGripError=0,slowed=0,capped=0;
for(const motion of ['idle','walk','run'])for(const sheathe of [false,true])for(const curved of [false,true])for(const cap of [0,5,360]){
 const action=sheathe?'sheathe':'draw',profile=saved[action+'Body']||{},bodyTargets=H.sanitize({...saved,...profile}).bodyTargets;
 const pose=H.motion(data,motion,70/60),arm=['upperarm_r','lowerarm_r','hand_r'].map(n=>data.names.indexOf(n)),top=data.names.indexOf('spine_05');
 const initial=P.measure(pose,arm,top,P.frame(pose,arm,top)),wanted=P.wrap(initial+(sheathe?65:-65));
 bodyTargets[sheathe?'clear':'seated'].pole=wanted;
 const curve=curved?[[.2,.03],[.4,.2],[.6,.82],[.8,.95]]:T.linear();
 const m=H.prepare(data,setup,{...saved,...profile,bodyTargets,motion,sheathe,startTick:70,entryInertia:0,maxElbowPoleAngularSpeed:cap,swordRelativeSlidePole:curved,[action+'Curve']:curve,[action+'SlideCurve']:curve});
 assert(m.plan.arrives,'hand completes reach');
 const keys=m.poleGuides.keys,start=keys[0],end=m.plan.endTick,duration=(end-start.tick)/60,delta=P.wrap(wanted-start.angle),speed=Math.min(cap,Math.abs(delta)/duration);
 for(let i=0;i<keys.length;i++){
  const k=keys[i];
  if(k.tick<=end){
   const expected=start.angle+Math.sign(delta)*speed*(k.tick-start.tick)/60,error=Math.abs(k.angle-expected);
   maxScheduleError=Math.max(maxScheduleError,error);assert(error<1e-7,'reach uses available time uniformly under the cap');
  }else{
   const prev=keys[i-1],f=H.sample(m,k.tick/60),expected=P.advance(prev.angle,P.target(bodyTargets,f.insertion),cap,1/240);
   assert(Math.abs(k.angle-expected)<1e-7,'sliding retains existing pursuit');
  }
  if(i)assert(Math.abs(k.angle-keys[i-1].angle)*240<=cap+1e-7,'general speed ceiling');
 }
 const atGrip=keys.find(k=>k.tick===end);
 if(speed<cap){assert(Math.abs(P.wrap(atGrip.angle-wanted))<1e-7,'arrives exactly with hand');assert(Math.abs(P.wrap(keys.find(k=>k.tick===end-.25).angle-wanted))>1e-7,'does not arrive early');slowed++;}
 else if(cap>0){assert(Math.abs(P.wrap(atGrip.angle-wanted))>1,'does not violate cap to force arrival');capped++;}
 for(let tick=end;tick<m.plan.slideEnd;tick+=.37){const f=H.sample(m,tick/60);maxGripError=Math.max(maxGripError,f.handError);assert(f.handError<.6);}
 cases++;
}
console.log(JSON.stringify({passed:true,cases,slowed,capped,maxScheduleError,maxGripError}));
