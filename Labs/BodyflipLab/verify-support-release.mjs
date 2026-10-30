// Support release must not count the same planted contact as a new landing.
import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./capsule.js'),P=require('./body-contact.js'),S=require('./support.js'),R=require('./recovery.js');
const checks=[],check=(label,ok)=>{assert(ok,label);checks.push(label);};
const axes=[[1,0,0],[0,1,0],[0,0,1]],q=[0,0,0,1],floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,5],.02);
const box=(name,center)=>({name,center,axes,half:[.1,.1,.1]});
for(const name of ['hand_r','hand_l','foot_r']){
 const shapes=p=>[box(name,p.points[1]),box('pelvis',p.points[2])];
 const body={move:(a,b,s,excluded)=>P.move(shapes(a).filter(x=>!excluded.includes(x.name)),shapes(b).filter(x=>!excluded.includes(x.name)),b.points[0],s),contacts:(p,s,bones)=>shapes(p).filter(x=>bones.includes(x.name)).flatMap(x=>s.map(surface=>P.query(x,surface)))};
 const make=otherContact=>{
  const source=t=>{const root=[0,-.05*t*t,0],h=t<=.1?.1:t<=.2?.1-.01*(t-.1):t<=.4?.099+2*(t-.2):.499-3*(t-.4),pelvisY=otherContact?1.1-5*t:2;return {root,pose:{points:[root,[0,h,0],[1,pelvisY,0]],q:[q,q,q],axes:[axes,axes,axes]},phase:t<=.1?'PUSH':'FALL',airTime:Math.max(0,t-.1),supportState:t<=.1?'PIN':'FREE'};};
  return K.track(source,{surfaces:[floor],body,bodyDuringSupport:true,supportAirborne:true,excludeBody:f=>f.supportState==='PIN'?[name]:[],speed:0,gait:t=>source(t).pose,fallPose:t=>source(t).pose});
 };
 const track=make(false);check(name+' lingering push contact is not landing',!track.sample(.15).returnedToLocomotion&&track.landings.length===0);
 check(name+' still physically collides during release',Math.min(...shapes(track.sample(.15).pose).map(s=>P.query(s,floor).gap))>=-1e-6);
 check(name+' lifts clear before rearming',!track.sample(.3).returnedToLocomotion&&P.query(shapes(track.sample(.3).pose)[0],floor).gap>.1);
 check(name+' later independent contact can land',track.sample(.6).returnedToLocomotion&&track.landings[0].bone===name&&track.landings[0].time>.4);
 const saved=JSON.stringify(track.sample(.15));track.sample(.7);track.sample(0);check(name+' reverse seek retains contact state',JSON.stringify(track.sample(.15))===saved);
 const interrupted=make(true);check(name+' other body contact is not suppressed',interrupted.sample(.22).returnedToLocomotion&&interrupted.landings[0].bone==='pelvis');
}
console.log(JSON.stringify({passed:true,checks},null,2));
