// Jump % controls COM launch energy, independently of the contact animation.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js'),I=require('./idle.js'),M=require('./mass.js'),Target=require('./target-rig.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),bytes=n=>{const b=fs.readFileSync(new URL(n,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),mass=M.model(names,parents,reference),run=I.create(read('data/idle.json'),bytes('data/idle.bin'),manifest).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),height=F.jumpHeight(jumps),target=Target.create(names,parents,reference),reports=[];
const fixtures=[...['foot','handBoth'].flatMap(pushWith=>[35,70,100,200,400].map(percent=>({pushWith,percent,spin:0}))),{pushWith:'foot',percent:200,spin:350},{pushWith:'handBoth',percent:200,spin:120},{pushWith:'foot',percent:70,spin:0,load:0}];
for(const fixture of fixtures){
 const {pushWith,percent,spin}=fixture,settings=C.sanitize({mode:'idle',ramps:false,surfaceIK:false,rebound:0,supportAlpha:0,loadMs:fixture.load??100,loadYMs:fixture.load??100,loadFullMs:fixture.load??100,platforms:[{id:'floor',position:[0,-.2,0],size:[20,.4,40],rotation:[0,0,0,1]}],jumpEvents:[{id:'push',time:.1,pushWith,jumpPercent:percent,flip:spin,twist:0,instantSpin:true,spinVersion:2}]}),seq=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:.8}),segment=seq.segments[0],release=segment.spinReleaseTime;
 assert.equal(seq.events[0].status,'Push',JSON.stringify(fixture));
 const first=segment.carrier.sample(release+1e-6),expected=Math.sqrt(19.62*height*percent/100),velocity=first.physical.velocity[1]+9.81e-6;
 assert(Math.abs(velocity-expected)<1e-8,'COM launch speed follows requested energy: '+JSON.stringify({fixture,velocity,expected}));
 const com=M.center(segment.rawSample(release+1e-6).pose,mass),at=release+expected/9.81,peak=M.center(segment.rawSample(at).pose,mass),rise=peak[1]-com[1]+velocity*1e-6;
 assert(Math.abs(rise-height*percent/100)<1e-7,'Ballistic height scales linearly with Jump %');
 assert.equal(first.physical.balanced,spin!==0,'Spinless jump must not change angular choreography');
 const before=target.project(segment.carrier.sample(release-1e-7).pose),after=target.project(segment.carrier.sample(release+1e-7).pose),seam=Math.max(...before.points.map((p,i)=>R.length(R.sub(p,after.points[i]))));
 assert(R.length(R.sub(M.center(before,mass),M.center(after,mass)))<1e-5,'No COM teleport at the launch impulse');
 assert(seam<.003,'Impulse changes velocity without teleporting position '+JSON.stringify({fixture,release,seam,points:before.points.map((p,i)=>({name:names[i],distance:R.length(R.sub(p,after.points[i]))})).filter(p=>p.distance>.0001)}));
 const stored=JSON.stringify(segment.rawSample(at));segment.rawSample(at+.1);segment.rawSample(release+.01);assert.equal(JSON.stringify(segment.rawSample(at)),stored,'Launch is seek-order independent');
 reports.push({...fixture,velocity,expected,rise,expectedRise:height*percent/100,seam});
}
const zeroSettings=C.sanitize({mode:'idle',ramps:false,surfaceIK:false,jumpEvents:[{id:'zero',time:.1,jumpPercent:0,flip:0,twist:0,spinVersion:2}]}),zero=F.sequence(run,jumps,zeroSettings,parents,reference,null,null,{horizon:.5});
assert.equal(zero.events[0].status,'Action');assert.equal(zero.sample(.3).physical,undefined,'Zero percent does not add a launch');
console.log(JSON.stringify({passed:true,height,cases:reports.length+1,reports},null,2));
