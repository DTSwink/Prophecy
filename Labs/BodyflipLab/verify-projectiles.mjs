import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js');globalThis.Recovery=R;
const {createPhysics}=await import('./physics.mjs'),manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),reference=C.poseFromShared(manifest),data=JSON.parse(fs.readFileSync(new URL('data/throws.json',import.meta.url))),physics=await createPhysics(manifest,reference);let checks=0;
const check=(ok,label)=>{assert(ok,label);checks++;},distance=(a,b)=>R.length(R.sub(a,b));
const plan={id:'test',kind:'bomb',scale:[1,1,1],releaseTime:.1333333,p:[0,10,10],q:[0,0,0,1],v:[3,2,5],omega:[0,0,0]};
try{
 physics.configure({dynamic:true,kinematic:true,surfaces:[],zeroGravity:false});physics.reset(reference);physics.setProjectiles(data.assets,[plan]);
 check(physics.projectilesAt(.1,()=>reference).length===0,'No released mesh before release');check(physics.projectileDiagnostics().steps===0,'No simulation before release');
 const seed=physics.projectilesAt(plan.releaseTime,()=>reference)[0];check(distance(seed.p,plan.p)<1e-5&&distance(seed.v,plan.v)<1e-5,'Exact fractional launch packet');
 const end=physics.projectilesAt(plan.releaseTime+1,()=>reference)[0];check(Math.abs(end.p[0]-3)<.01&&Math.abs(end.p[2]-15)<.01,'World launch velocity preserved');check(Math.abs(end.p[1]-(10+2-4.905))<.06,'Same-world gravity advances released object');
 const steps=physics.projectileDiagnostics().steps,prefix=JSON.stringify(physics.projectilesAt(.5,()=>reference));physics.projectilesAt(plan.releaseTime+1,()=>reference);check(physics.projectileDiagnostics().steps===steps,'Paused/cached redraw does no physics work');check(JSON.stringify(physics.projectilesAt(.5,()=>reference))===prefix,'Reverse seek reuses deterministic cached state');
 check(physics.diagnostics().bodies===25,'Projectile does not create second agent/world');
 physics.configure({dynamic:true,kinematic:false,surfaces:[],zeroGravity:true});physics.reset(reference);physics.setProjectiles(data.assets,[{...plan,id:'sim',releaseTime:.123,p:[0,10,10]}]);for(let i=1;i<=60;i++)physics.step(reference,1/240,i/240);
 const sim=physics.projectileStates(.25)[0];check(!!sim&&distance(sim.p,[3*(.25-.123),10+2*(.25-.123),10+5*(.25-.123)])<.01,'Simulated mode shares stepping and fractional launch');
 check(physics.projectileDiagnostics().clock>=.25-1e-9,'Projectile clock uses absolute lab time');
 console.log(JSON.stringify({passed:true,checks,kinematicSteps:steps,simulated:sim}));
}finally{physics.dispose();}
