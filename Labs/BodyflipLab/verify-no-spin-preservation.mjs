// Accepted zero-spin space motion is an exact compatibility path.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),G=require('./space-gym.js'),A=require('./attack-aim.js'),T=require('./throw-attack.js'),Target=require('./target-rig.js'),I=require('./idle.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),run=I.create(read('data/idle.json'),bytes('data/idle.bin'),m).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(p=>read(p).clips).map(F.decodeJump),catalog=new Map(read('data/vanilla.json').clips.map(meta=>[meta.name,C.decode(meta,bytes(meta.file),names,parents)]));T.load(read('data/throws.json'));
// Reconstruct only the pre-physicalization composition. All attack algorithms
// remain the same current modules; no historical Git revision is substituted.
let original=fs.readFileSync(new URL('space-gym.js',import.meta.url),'utf8');
const start=original.indexOf('const raw=segment.spin.sample,config='),end=original.indexOf('  segment.pushDebug',start);assert(start>=0&&end>start,'Locate only the physical wrapper');
original=original.slice(0,start)+'segment.sample=segment.spin.sample;\n'+original.slice(end);
const orientation='segment.sample.atOrientation=segment.spin.active?(t,rotation)=>O.rebase(segment.sample(t),rotation,rig):segment.spin.atOrientation;';assert(original.includes(orientation));original=original.replace(orientation,'segment.sample.atOrientation=segment.spin.atOrientation;');
const prior={exports:{}};new Function('module','require',original)(prior,require);const before=prior.exports,projector=Target.create(names,parents,reference),project=p=>projector.project(p);
function aimed(sequence,name,settings){
 const track=sequence.segments[0].attack,sampleHit=t=>sequence.sample(t).pose,launchAt=track.launchAt?(p,map=x=>x)=>track.launchAt(p,track.transportVelocity(t=>map(sampleHit(t),t))):null;
 const plan=A.create({clip:catalog.get(name),track,names,parents,reference,sampleHit,launchAt,project});
 return t=>project(plan.apply(sampleHit(t),t,settings.target,settings.aimWeight,settings.undoRotation));
}
const reports=[];let samples=0;const started=performance.now();
for(const name of [...catalog.keys(),'big-throw','small-throw']){
 const settings=C.sanitize({mode:'spaceGym',aim:true,aimWeight:.8,airFlip:false,momentum3D:true,kickToArmed:true,pelvisAttackCompensation:1,target:[-1,1.6,-2],jumpEvents:[{id:'attack',time:.1,jumpPercent:0,flip:0,twist:0,spinVersion:2,attack:name,throwCharge:37}]}),events=settings.jumpEvents;
 const old=before.sequence(run,jumps,settings,parents,events,catalog,reference),current=G.sequence(run,jumps,settings,parents,events,catalog,reference),axis=G.sequence(run,jumps,{...settings,momentum3D:false},parents,events,catalog,reference),track=current.segments[0].attack;
 const oldAim=aimed(old,name,settings),newAim=aimed(current,name,settings),end=track.returnEnd+.05;
 const times=[0,.1,track.start,track.hitTime,track.returnEnd,...Array.from({length:31},(_,i)=>end*i/30)];
 for(const t of times){
  const a=old.sample(t),b=current.sample(t),c=axis.sample(t);assert.deepEqual(b,a,`${name} global source at ${t}`);assert.deepEqual(c,a,`${name} axis-only source at ${t}`);
  assert.deepEqual(newAim(t),oldAim(t),`${name} aimed displayed pose at ${t}`);assert.equal(b.physicalAim,undefined);samples++;
 }
 const t=track.start+(track.hitTime-track.start)*.6,snapshot=JSON.stringify(current.sample(t));current.sample(end);current.sample(0);assert.equal(JSON.stringify(current.sample(t)),snapshot,`${name} reverse seek`);
 assert.equal(current.segments[0].physical.track,null,`${name} must not initialize physical solver`);reports.push({name,end,samples:times.length});
}
const result={passed:true,attacks:reports.length,samples,exactGlobalSource:true,exactAimedDisplay:true,physicalTracksCreated:0,elapsedMs:performance.now()-started,reports};fs.writeFileSync(new URL('../../Saved/Diagnostics/BodyflipPort20261030/no-spin-preservation.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({...result,reports:undefined},null,2));
