// Exercise the production arrow/seek/tick/contact paths with a known foot trajectory.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js');
const source=fs.readFileSync(new URL('app.js',import.meta.url),'utf8');
const blocks=[['function previewSeek(', 'function finishPreview('],['function placeKinematic(', 'function restartTrim('],['function displayedAttack(', 'async function ensurePrepared('],['async function seek(', 'function animate(']];
const queue=new Map(),checks=[];let nextId=0,pose=null,steps=0,draws=0;
const check=(name,value)=>{assert(value,name);checks.push(name);};
const ctx={C,norm:R.length,sub:R.sub,performance,setTimeout,
 settings:{motion:'kinematic',attack:'kickL',target:[0,0,0],radius:.1,trimIn:0,trimOut:10/60,flipAngle:0,twistAngle:0,flipSpeed:0,twistSpeed:0,attackRate:1},
 simTime:0,attackTime:-1,flip:0,twist:0,flight:{segments:[]},flightFrame:null,clip:{duration:1},
 hit:false,bestMiss:Infinity,previousContact:null,contactAttackKey:null,currentPose:null,desiredPose:null,manualResponse:null,
 previewRAF:null,previewTime:0,previewAdvance:false,playRevision:0,seekRevision:0,seeking:false,playing:false,loadingRun:false,
 requestAnimationFrame(fn){const id=++nextId;queue.set(id,fn);return id;},
 setPlaying(value){ctx.playing=value;},ensurePrepared:async()=>{},drawAll(){draws++;},fail(e){throw e;},
 targetPose(){const frame=Math.round(ctx.simTime*60);ctx.flightFrame={attack:{name:'kickL',start:0,phase:frame>=1&&frame<=8?'ATTACK':'RETURN'}};return {point:[[ -2, -1, 1, 2, 0, 3, 4, 5, 6, 7, 8 ][frame]??8,0,0]};},
 attackContact:p=>p.point,total:()=>2,
 physics:{reset(p){pose=p;},step(p){steps++;pose=p;},read(){return pose;}},
};
vm.createContext(ctx);
for(const [start,end] of blocks){const a=source.indexOf(start),b=source.indexOf(end,a);assert(a>=0&&b>a);vm.runInContext(source.slice(a,b),ctx);}
async function flush(){const callbacks=[...queue.values()];queue.clear();for(const fn of callbacks)fn();await new Promise(r=>setImmediate(r));assert.equal(ctx.seeking,false);}
async function arrow(direction=1){ctx.stepFrame(direction);await flush();}

await ctx.seek(1/60);check('A clear starting pose is pink',!ctx.hit);
ctx.tick();const play={hit:ctx.hit,miss:ctx.bestMiss};
await ctx.seek(1/60);ctx.playing=true;await arrow();
check('Forward arrow matches Play swept contact between frames',ctx.hit&&ctx.hit===play.hit&&ctx.bestMiss===play.miss);
check('Arrow stepping leaves playback paused',!ctx.playing);
await arrow();check('Forward steps retain an earlier hit',ctx.hit);
await arrow(-1);await arrow(-1);check('Rewinding clears hits from later frames',!ctx.hit);

await ctx.seek(0);const before=steps;
for(let i=0;i<3;i++)ctx.stepFrame(1);
await flush();
check('Held arrows process all queued frames',steps-before===3&&Math.round(ctx.simTime*60)===3);
check('Held arrows detect a crossing before the final frame',ctx.hit);
await ctx.seek(4/60);check('Direct seek evaluates contact at the selected frame',ctx.hit);
await ctx.seek(1/60);await ctx.seek(3/60);
check('Direct seek does not sweep across unrelated positions',!ctx.hit);

await ctx.seek(1/60);for(let i=0;i<8;i++)ctx.stepFrame(1);await flush();
check('A hit remains green into return when stepping forward',ctx.hit&&ctx.flightFrame.attack.phase==='RETURN');
await arrow();await arrow();check('Wrapping to trim start clears the previous pass',!ctx.hit&&ctx.simTime===0);
await ctx.seek(1/60);ctx.stepFrame(1);ctx.stepFrame(-1);await flush();
check('Mixed forward/back input does not retain a cancelled crossing',!ctx.hit&&Math.round(ctx.simTime*60)===1);
check('Steps redraw the target indicator',draws>0);
console.log(JSON.stringify({passed:true,checks:checks.length,details:checks},null,2));
