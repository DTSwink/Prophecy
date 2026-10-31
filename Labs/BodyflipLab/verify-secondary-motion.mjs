// Smooth and instantaneous spin share one secondary response; no GUI or physics worker.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),O=require('./spin.js'),M=require('./mass.js'),J=require('./joint-rig.js');
const m=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),{names,parents}=m,reference=C.poseFromShared(m),mass=M.model(names,parents,reference),joints=J.create(names,parents,reference),settings=C.sanitize({spinInertia:0}),source=()=>({pose:reference,root:reference.points[0],phase:'SPACE'});
let checks=0;const check=(ok,label)=>{assert(ok,label);checks++;},dist=(a,b)=>R.length(R.sub(a,b)),reports=[];
check(settings.spinLag===.6,'New scenes have default secondary motion');check(C.sanitize({spinLag:0}).spinLag===0,'Explicit zero remains disabled');
for(const turnAxis of [0,3,7])for(const turnIn of [.05,.4,1]){
 const event={spinVersion:2,flip:240,twist:120,turnAxis,turnIn,turnDelay:.0713,instantSpin:false},soft=O.create(source,{event,settings,names,parents,reference}),hard=O.create(source,{event,settings:{...settings,spinLag:0},names,parents,reference});let offset=0,maxCom=0;
 for(let f=0;f<=90;f++){const t=f/60,a=soft.sample(t),b=hard.sample(t);offset=Math.max(offset,...a.pose.points.map((p,i)=>dist(p,b.pose.points[i])));maxCom=Math.max(maxCom,dist(M.center(a.pose,mass),M.center(reference,mass)));check(a.pose.points.flat().concat(a.pose.q.flat()).every(Number.isFinite),'Finite smooth recoil');check(Math.abs(a.spin.flip-b.spin.flip)<1e-6&&Math.abs(a.spin.twist-b.spin.twist)<1e-6,'Recoil does not slow angular command');if(f%15===0)check(joints.inspect(a.pose).every(j=>j.angularError<1e-8&&j.anchorError<1e-9),'Jolt limits retained');}
 check(offset>.001&&offset<.32,'Visible bounded smooth response');check(maxCom<1e-11,'No invented COM force');const snap=JSON.stringify(soft.sample(.31));soft.sample(2);soft.sample(.05);check(snap===JSON.stringify(soft.sample(.31)),'Reverse seeking deterministic');reports.push({turnAxis,turnIn,maxOffset:offset,maxCom});
}
const stationary=O.create(source,{event:{spinVersion:2,flip:0,twist:0},settings,names,parents,reference});check(!stationary.active&&stationary.sample(1).pose===reference,'No secondary work for zero spin');
console.log(JSON.stringify({passed:true,checks,reports},null,2));
