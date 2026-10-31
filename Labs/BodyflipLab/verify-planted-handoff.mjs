import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./capsule.js'),P=require('./body-contact.js'),S=require('./support.js');
const axes=[[1,0,0],[0,1,0],[0,0,1]],floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,5],.02);
const pose=root=>({points:[root,[root[0],root[1]+.9,0]],q:[[0,0,0,1],[0,0,0,1]],axes:[axes,axes]});
let checks=0;
for(const bone of ['ball_r','foot_r','hand_r','head'])for(const state of ['PIN','APPROACH','FREE']){
 const shape=p=>({name:bone,center:p.points[1],axes,half:[.1,.1,.1]}),body={move:(a,b,s)=>P.move([shape(a)],[shape(b)],b.points[0],s),contacts:(p,s)=>s.map(surface=>({...P.query(shape(p),surface),bone,surface}))};
 const source=t=>{const age=Math.max(0,t-.6),y=t<.6?.2-2*t:-1+4*age-4.905*age*age,root=[0,y,0];return {...(t>=.6?{physical:{com:pose(root).points[1],velocity:[0,4-9.81*age,0]}}:{}),root,pose:pose(root),phase:t<.6?'LOAD':'FALL',supportState:t<.6?state:'FREE',airTime:1+t,vy:t<.6?-2:4-9.81*age};};
 const track=K.track(source,{body,surfaces:[floor],speed:0,bodyDuringSupport:true,supportAirborne:true,forceSource:true,gait:()=>pose([0,0,0]),fallPose:()=>pose([0,0,0])}),held=state==='PIN'&&bone!=='head';
 assert.equal(track.sample(.55).returnedToLocomotion,!held,bone+'/'+state+' contact ownership');checks++;
 if(held){assert(track.sample(.55).pose.points[1][1]>=.1-1e-6,'Collision still prevents penetration');assert(!track.sample(.8).returnedToLocomotion,'Push can leave the platform');assert.equal(track.sample(1.1).phase,'RISE','Phase includes collision velocity carry');checks++;assert(track.sample(2.5).returnedToLocomotion,'Later fall still lands after support lifts clear');checks+=3;}
}
console.log(JSON.stringify({passed:true,checks}));
