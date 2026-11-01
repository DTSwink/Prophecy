import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),I=require('./idle.js'),T=require('./throw-attack.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),run=I.create(read('data/idle.json'),bytes('data/idle.bin'),m).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(p=>read(p).clips).map(F.decodeJump),catalog=new Map(read('data/vanilla.json').clips.map(meta=>[meta.name,C.decode(meta,bytes(meta.file),names,parents)]));T.load(read('data/throws.json'));
const settings=C.sanitize({mode:'spaceGym',aim:true,aimWeight:1,momentum3D:false,trimOut:1.1,jumpEvents:[{id:'a',time:.1,jumpPercent:0,flip:120,twist:0,attack:'slashL',spinVersion:2}]}),generate=()=>{throw Error('Space needs no NN');};
const direct=await F.prepare(run,jumps,settings,parents,reference,generate,()=>false,catalog);
let beats=0,last=performance.now(),longest=0;const timer=setInterval(()=>{const now=performance.now();longest=Math.max(longest,now-last);last=now;beats++;},8);
const cooperative=await F.prepare(run,jumps,settings,parents,reference,generate,()=>false,catalog,{cooperative:true});clearInterval(timer);
assert(beats>0,'Preparation must give timer/input tasks a turn');
let maxDifference=0;for(let i=0;i<=66;i++){const a=direct.sample(i/60),b=cooperative.sample(i/60);for(const key of ['points','q'])for(let j=0;j<a.pose[key].length;j++)for(let k=0;k<a.pose[key][j].length;k++)maxDifference=Math.max(maxDifference,Math.abs(a.pose[key][j][k]-b.pose[key][j][k]));}
assert(maxDifference<1e-9,'Yielding must preserve the exact motion');
await cooperative.extend(1.3);assert(cooperative.preparedThrough>=1.3);assert.equal(cooperative.events.length,1,'Extending must not duplicate markers');
let cancel=false;setTimeout(()=>{cancel=true;},0);const stopped=await F.prepare(run,jumps,{...settings,trimOut:1.2},parents,reference,generate,()=>cancel,catalog,{cooperative:true});assert.equal(stopped,null,'A newer edit must cancel preparation at a work boundary');
console.log(JSON.stringify({passed:true,samples:67,maxDifference,timerTurns:beats,longestTimerGapMs:longest,cancelled:true,extension:true}));
