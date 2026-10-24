import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js');globalThis.Recovery=R;
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),m=read('data/manifest.json'),jumps=read('data/jumps.json').clips.map(F.decodeJump),run=F.decodeNN(read('data/run-default.json'));
const idle=C.poseFromShared(m),f=R.rotate(idle.q[1],[0,-1,0]),base=R.qm(R.fromTo(R.unit([f[0],0,f[2]]),[0,0,1]),idle.q[1]);
const {createPhysics}=await import('./physics.mjs');const p=await createPhysics(m,C.centerPose(idle,base));
const settings={...C.defaults,fallCap:12},flight=F.create(run,jumps,settings,m.parents,idle),receipt={cases:[],maxAnchor:0,maxPelvisError:0,maxDownSpeed:0,maxPelvisAngle:0};
p.configure({dynamic:true,edge:flight.edge,cap:settings.fallCap});p.reset(flight.sample(0).pose,[0,0,flight.speed]);
assert(p.simulated);assert.equal(p.diagnostics().dynamicBodies,25);let peak=-Infinity;
for(let n=1;n<=240*12;n++){
 const t=n/240,s=flight.sample(t);p.step(s.pose,1/240);const d=p.diagnostics(),pose=p.read(),velocity=p.com(true);assert(d.finite);peak=Math.max(peak,pose.points[1][1]);
 receipt.maxPelvisAngle=Math.max(receipt.maxPelvisAngle,R.length(R.qlog(R.qm(pose.q[1],R.qinv(s.pose.q[1]))))*180/Math.PI);receipt.maxAnchor=Math.max(receipt.maxAnchor,d.anchorError);receipt.maxPelvisError=Math.max(receipt.maxPelvisError,R.length(R.sub(pose.points[1],s.pose.points[1])));receipt.maxDownSpeed=Math.max(receipt.maxDownSpeed,-velocity[1]);
 assert(velocity[1]>=-settings.fallCap-.0001,'COM terminal cap');
 if(n%240===0)receipt.cases.push({t,phase:s.phase,com:p.com(),velocity,anchor:d.anchorError,pelvisError:R.length(R.sub(pose.points[1],s.pose.points[1]))});
}
receipt.peakPelvis=peak;receipt.edge=flight.edge;receipt.apex=flight.apex;receipt.jump=flight.start;
assert(receipt.maxPelvisAngle<25,`pelvis rotation ${receipt.maxPelvisAngle}`);assert(receipt.maxAnchor<.015,`anchor ${receipt.maxAnchor}`);assert(receipt.maxPelvisError<.3,`pelvis ${receipt.maxPelvisError}`);assert(peak>1.4);assert(p.com()[1]<-50);assert.equal(flight.sample(12).phase,'FALL LOOP');
// Root rise is exactly the selected source curve; fall-loop root motion never accumulates twice.
const sample=flight.sample(flight.jumpStart+flight.apex);assert(Math.abs(sample.root[1]-(1.033+.055))<.003);
for(const cap of [2,12,50]){let last=0;for(let t=0;t<30;t+=.01){const fall=F.cappedFall(t,cap);assert(fall.v>=-cap-1e-9);assert(fall.y<=last+1e-9);last=fall.y;}}
// Physics can return to the original space experiment with a kinematic pelvis.
p.configure();p.reset(C.centerPose(idle,base));p.step(C.centerPose(idle,base),1/240);assert(!p.simulated);assert(p.diagnostics().finite);p.dispose();
fs.writeFileSync(new URL('flight-verification.json',import.meta.url),JSON.stringify(receipt,null,2));console.log(JSON.stringify({passed:true,maxAnchor:receipt.maxAnchor,maxPelvisError:receipt.maxPelvisError,maxDownSpeed:receipt.maxDownSpeed,peak:receipt.peakPelvis,maxPelvisAngle:receipt.maxPelvisAngle}));
