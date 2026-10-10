const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),lab=path.join(root,'Labs/SwordHolsterLab');
const H=require(path.join(lab,'holster.js')),B=require(path.join(lab,'bodyreach.js')),FK=require(path.join(lab,'armfk.js')),Head=require(path.join(lab,'headlook.js')),Return=require(path.join(lab,'fkreturn.js')),R=require(path.join(lab,'recovery.js')),Curve=require(path.join(lab,'retime.js'));
const data=require(path.join(lab,'data/motions.json')),setup=require(path.join(lab,'data/unreal-setup.json')),o=require(path.join(root,'Tools/Recovery/SwordLabCheckpoint20261010/lab-state.json')).parameters;
const rows=[];
for(const motion of ['idle','walk'])for(const sheathe of [false,true]){
 const model=H.prepare(data,setup,{...o,motion,sheathe}),base=H.motion(data,motion,o.startTick/60),ctx=B.make(data,base),arm=model.arm,frame=model.sourceFrames[o.startTick],retained=1-o.shrinkPercent/100,full=H.compose(setup.seated,frame.holster),seat=H.seatHandAtScale(setup,full,retained),clear={...seat,p:R.sub(seat.p,R.mul(R.rotate(full.q,[0,0,1]),setup.bladeLength*retained))},mouth=R.add(full.p,R.rotate(full.q,setup.baseBladeLocal.map((x,i)=>x*full.s[i])));
 const body=B.optimize(ctx,base,clear.p,[0,0,0],o.spineClavicleAngleLimit),source=FK.capture(base,arm,data.parents),end=B.apply(ctx,base,body);H.solve(end,arm,sheathe?clear:seat);const destination=FK.capture(end,arm,data.parents);
 let state={},heads=[];for(let tick=0;tick<=180;tick++){const f=Head.step(Head.make(data),base,base,mouth,state,{tick,startTick:0,lookOutTick:90,maxLookIn:o.maxHeadLookInVelocity,maxLookOut:o.maxHeadLookOutVelocity,lookAtAlpha:o.headLookAtAlpha,lookInExponent:o.headLookInExponent,lookOutExponent:o.headLookOutExponent});state=f.state;heads.push(state.q);}
 const before=FK.apply(B.apply(ctx,base,body),arm,data.parents,FK.blend(source,destination,.995)),returns=[];
 for(const worldInertia of [false,true])for(const springReturn of [false,true])for(const upperArmTwistRemoval of [0,1]){
  const profile={...o[sheathe?'sheatheReturn':'drawReturn'],worldInertia,springReturn,upperArmTwistRemoval},ret=Return.prepare({names:data.names,parents:data.parents,last:end,previous:before,base,previousBase:base,dt:1/60,profile});
  returns.push({world:worldInertia,spring:springReturn,twist:upperArmTwistRemoval,duration:ret.timing.duration,samples:[.1,.3,.7,1].map(f=>({time:f*ret.timing.duration,pose:Return.sample(ret,base,f*ret.timing.duration)}))});
 }
 rows.push({motion,sheathe,base,body,clear,seat,mouth,source,destination,duration:FK.duration(source,destination,o.maxReachSpeed,o.maxReachRotationSpeed),heads,end,before,returns});
}
const curves=['drawCurve','sheatheCurve','drawSlideCurve','sheatheSlideCurve'].map(key=>({key,points:o[key],values:Array.from({length:101},(_,i)=>Curve.sample(Curve.prepare(o[key]),i/100))}));
const file=path.join(root,'Saved/Diagnostics/SwordLabPort20261010/parity.json');fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify({names:data.names,parents:data.parents,rows,curves,profile:o}));console.log(file);
