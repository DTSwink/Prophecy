// Entry is part of the planned trajectory, with no display-only teleport.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import {sourceRuntime} from './source-runtime-test.mjs';
const assets=JSON.parse(fs.readFileSync('Content/BodyflipLab/Assets.json','utf8'));
const report=JSON.parse(fs.readFileSync('Saved/Diagnostics/BodyflipPort20261030/NativeHost/Saved/Diagnostics/BodyflipPort20261030/agent-jolt.json','utf8'));
const ctx=vm.createContext({console,__bodyflipAttack:id=>fs.readFileSync('Content/BodyflipLab/Attacks/'+id+'.json','utf8'),__bodyflipNN:()=>{throw Error('Entry fixture must not infer');}});
vm.runInContext(sourceRuntime().runtime,ctx);vm.runInContext(fs.readFileSync('Tools/Bodyflip/runtime-adapter.js','utf8'),ctx);
const B=ctx.BodyflipNative.raw,R=ctx.BodyflipRequire('BodyflipLab/recovery.js'),C=ctx.BodyflipRequire('BodyflipLab/core.js');B({op:'assets',value:assets});
const original=report.frames[12].canonical.pose,origin=original.points[0],entry={points:original.points.map(p=>R.sub(p,origin)),q:original.q};
let checks=0;for(const mode of ['idle','spaceGym']){
 B({op:'start',rigProfile:report.nativeRigProfile,settings:{mode,nativeEntry:entry,trimOut:.3,jumpBlend:.2,aim:false,ramps:false,platforms:[],jumpEvents:[]},horizon:.3});
 const start=B({op:'sample',time:0}),relative=start.pose.points.map(p=>R.sub(p,start.root));
 for(let i=1;i<assets.names.length;i++){assert(R.length(R.sub(relative[i],entry.points[i]))<1e-8,mode+' first position '+assets.names[i]);assert(R.length(R.qlog(R.qm(start.pose.q[i],R.qinv(entry.q[i]))))<1e-7,mode+' first rotation '+assets.names[i]);checks+=2;}
 const tiny=B({op:'sample',time:1e-5});assert(R.length(R.sub(tiny.pose.points[1],start.pose.points[1]))<1e-6,'Held entry has zero initial velocity');checks++;
 const saved=JSON.stringify(B({op:'sample',time:.15}));B({op:'sample',time:.3});B({op:'sample',time:0});assert.equal(JSON.stringify(B({op:'sample',time:.15})),saved,'Reverse seek keeps entry');checks++;
}
// Failed bend feasibility must leave the original inertial transition intact.
const parents=[-1,0,1,2],names=['root','upperarm_l','lowerarm_l','hand_l'];
const local={p:[[0,0,0],[0,0,0],[1,0,0],[1,0,0]],q:[[0,0,0,1],[0,0,0,1],R.qexp([0,0,.5]),[0,0,0,1]]},seed=R.fk(local,parents);C.registerRig(names,parents,seed);
const incoming=t=>{const p=structuredClone(local);p.q[2]=R.qexp([0,0,.5-60*t]);return R.fk(p,parents);};
const blended=C.transition(()=>seed,incoming,.2,parents,null,false,true),h=1e-5;
assert(R.length(R.qlog(R.qm(blended(h).q[2],R.qinv(seed.q[2]))))/h<.02,'Impossible bend must not disable velocity cancellation');checks++;
console.log(JSON.stringify({passed:true,checks}));
