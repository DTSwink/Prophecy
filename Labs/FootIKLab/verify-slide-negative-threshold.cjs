'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),{createRequire}=require('module');
const K=require('./footik.js'),local=createRequire(__filename),box={module:{exports:{}},require:local,console};
vm.runInNewContext(fs.readFileSync(require.resolve('./surface.js'),'utf8').replace('const api={settings,','const api={createRootMotion,settings,'),box);
const S=box.module.exports;
assert.equal(K.sanitize({slideSpeed:-1}).slideSpeed,-1);
assert.equal(K.sanitize({slideSpeed:''}).slideSpeed,2);
function scenario(threshold){
 const s=S.settings({terrain:'incline',approach:'parallel',slopeAngle:90,minGravityIncline:80,slideEnabled:true,slideSpeed:threshold,inclineGravity:true}),terrain=S.createTerrain(s),events=[];
 const options={s,terrain,height:.9,speed:2,events};let motion=S.createRootMotion(options),time=0;
 function tick(vy){if(vy!==undefined){const saved=motion.snapshot();saved.velocity=[0,vy,0];motion=S.createRootMotion(options,saved);}const c=motion.begin(time);motion.finish(c,[]);time+=1/120;return c;}
 return {tick,events,snapshot:()=>motion.snapshot(),restore:saved=>{motion=S.createRootMotion(options,saved);}};
}
const early=scenario(-1);
assert(!early.tick(2).slide);
const entry=early.tick(.95);assert(entry.slide&&entry.velocity[1]>0,'Enter before apex');
const next=early.tick();assert(next.slide,'Do not immediately exit while still rising');
assert(Math.abs(next.velocity[1]-(entry.velocity[1]-9.81/120))<1e-10,'Full gravity, no upward thrust');
const saved=early.snapshot();const whole=early.tick();early.restore(saved);const continued=early.tick();
assert.equal(!!whole.slide,!!continued.slide,'Restored early-ascent latch retained');
assert(Math.abs(whole.velocity[1]-continued.velocity[1])<1e-10);
assert(early.tick(-.1).slide);assert(!early.tick(.2).slide,'New ascent after falling exits');
assert(!early.tick(.3).slide,'Increasing ascent cannot immediately re-enter');
assert(early.tick(.25).slide,'Slowing ascent below negative threshold can re-enter');
const positive=scenario(2);assert(!positive.tick(1).slide);assert(!positive.tick(-1).slide);assert(positive.tick(-2.1).slide);assert(!positive.tick(.1).slide);
const zero=scenario(0);assert(!zero.tick(0).slide);assert(zero.tick(-.01).slide);
console.log('PASS: signed thresholds, early-ascent hold, gravity, restore, reversal/re-entry, positive and zero compatibility');
