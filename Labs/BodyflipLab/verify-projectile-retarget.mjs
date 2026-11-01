import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js');globalThis.Recovery=R;
const {createPhysics}=await import('./physics.mjs'),manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),reference=C.poseFromShared(manifest),data=JSON.parse(fs.readFileSync(new URL('data/throws.json',import.meta.url))),physics=await createPhysics(manifest,reference);
const scaleOf=(attack,kind)=>{const s=data.settings.weaponScales[attack][kind];return Array.isArray(s)?s:[s,s,s];};
let completed=0;
physics.configure({dynamic:true,kinematic:true,surfaces:[],zeroGravity:true});physics.reset(reference);
for(const [attack,kind,override] of [['big-throw','spear'],['small-throw','bomb'],['small-throw','bomb',[.8,1.1,.9]]]){
 const scale=override||scaleOf(attack,kind);
 for(let i=0;i<12;i++){
  const plan={id:'retarget:'+kind,kind,scale,releaseTime:.1,p:[0,10,10],q:[0,0,0,1],v:[3+i*.1,2,5],omega:[0,0,0]};
  physics.setProjectiles(data.assets,[plan]);const state=physics.projectilesAt(.3,()=>reference)[0];assert(state.p.concat(state.q,state.v).every(Number.isFinite));assert.equal(physics.projectileDiagnostics().bodies,1);completed++;
  const cached=JSON.stringify(physics.projectilesAt(.3,()=>reference)),steps=physics.projectileDiagnostics().steps;assert.equal(JSON.stringify(physics.projectilesAt(.3,()=>reference)),cached);assert.equal(physics.projectileDiagnostics().steps,steps);
 }
}
physics.setProjectiles(data.assets,[]);assert.equal(physics.projectileDiagnostics().bodies,0);physics.dispose();console.log({passed:true,retargets:completed,disposed:true});
