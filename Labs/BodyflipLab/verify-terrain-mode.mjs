import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),T=require('./terrain-mode.js'),S=require('./scenes.js'),R=require('./recovery.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),m=read('data/manifest.json'),idle=C.poseFromShared(m),jumps=[...read('data/jumps.json').clips,...read('data/jumps-standing.json').clips].map(F.decodeJump);
const origin=process.env.BODYFLIP_URL||'http://127.0.0.1:8876',realFetch=fetch;globalThis.fetch=(p,o)=>realFetch(p.startsWith('http')?p:origin+'/foot-ik/'+p,o);
const post=async(path,data)=>{const r=await realFetch(origin+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),v=await r.json();assert(r.ok,v.error);return v;};
const previous=S.snapshot({settings:C.sanitize({mode:'spaceGym',platforms:[],flipSpeed:400,jumpEvents:[{time:1,flip:400,spinVersion:2}]}),playback:{time:1,playing:true}}),switched=S.switchMode(previous,'footIK'),restored=S.switchMode(switched,'spaceGym');assert.deepEqual(restored.settings,previous.settings);assert.deepEqual(restored.playback,previous.playback);
const s=C.sanitize({...(process.argv.includes('--saved')?read('state.json').settings:C.defaults),...T.preset()}),run=F.decodeNN(await post('/run',{gait:'run',duration:5,phase:s.runPhase,drawn:false})),carrier=await T.prepare(s,m.parents,post),flight=await F.prepare(run,jumps,s,m.parents,idle,d=>post('/resume',d),()=>false,null,{locomotion:carrier});
assert.equal(flight.events[0].status,'Push');const segment=flight.segments[0],release=segment.spinReleaseTime;
assert(carrier.model.sample(release).surface.velocity[1]>0,'Leave while still climbing');assert(!carrier.model.sample(release).slide,'Leave before sliding');
const target=require('./target-rig.js').create(m.names,m.parents,idle),display=t=>target.project(flight.sample(t).pose,flight.surfaces);
// A better knee angle alone is not a contact fix: skipping acquisition also
// passed the old test while the shoe slid along the wall. Require a sustained
// material plant, then check that final display projection preserves it.
const right=['thigh_r','calf_r','foot_r'].map(n=>m.names.indexOf(n));
const kneeBend=p=>{const [h,k,f]=right,a=R.unit(R.sub(p.points[k],p.points[h])),b=R.unit(R.sub(p.points[f],p.points[k]));return Math.acos(Math.max(-1,Math.min(1,R.dot(a,b))))*180/Math.PI;};
const contactBends=Array.from({length:9},(_,i)=>kneeBend(display(.3+i/240)));
const wallEvents=carrier.model.events.filter(e=>e.surface==='incline'&&e.frame/60<segment.preparationStart);
const firstPlant=wallEvents.find(e=>e.type==='plant'&&e.side==='R');
assert(firstPlant,'First right wall step has no material lock: sliding support is not a planted foot');
const firstRelease=carrier.model.events.find(e=>e.type==='release'&&e.side==='R'&&e.frame>=firstPlant.frame);
const plantEnd=Math.min(segment.preparationStart,firstRelease?.frame/60??Infinity);
assert(plantEnd-firstPlant.frame/60>=.1,'First right wall plant is too brief to support the step');
let displayedPinError=0;
for(let i=Math.ceil(firstPlant.frame*2);i<plantEnd*120-1e-8;i++){
 const c=carrier.model.frames[i].feet.find(f=>f.side==='R').contact;
 assert(c?.surface==='incline','Right foot loses its wall lock during stance');
 const p=display(i/120),point=R.add(p.points[right[2]],R.rotate(p.q[right[2]],c.localPoint));
 displayedPinError=Math.max(displayedPinError,R.length(R.sub(point,c.point)));
}
assert(displayedPinError<.002,'Bodyflip final projection moves the planted material point');
for(let i=0;i<wallEvents.length;i++){const e=wallEvents[i];if(e.type!=='plant')continue;const release=wallEvents.slice(i+1).find(x=>x.type==='release'&&x.side===e.side);assert(!release||release.reason!=='reach'||(release.frame-e.frame)/60>1/30,'Wall pin immediately exhausts reach');}
assert(carrier.model.frames.slice(33,41).every(f=>f.surface.contacts>0),'First wall step loses support');
const rows=[];let largestStep=0,prev=null;
for(let i=0;i<=Math.round(s.trimOut*240);i++){const t=i/240,f=flight.sample(t);assert(f.pose.points.flat().every(Number.isFinite)&&f.pose.q.flat().every(Number.isFinite));const shown=display(t);if(prev)largestStep=Math.max(largestStep,...shown.points.slice(1).map((p,j)=>R.length(R.sub(p,prev.points[j+1]))));prev=shown;rows.push(JSON.stringify(f.pose));if(t<segment.preparationStart)assert.deepEqual(f.pose,carrier.sample(t).pose);if(t>release+.02&&t<1.5)assert(!f.footIK,'No terrain corrections during flip');}
for(let i=rows.length-1;i>=0;i-=7)assert.equal(JSON.stringify(flight.sample(i/240).pose),rows[i],'Reverse seek changes motion');

const boundaries=[segment.preparationStart,segment.contactTime,segment.jumpStart,release,...segment.carrier.landings.map(l=>l.time)],joins=boundaries.map(t=>{const a=display(t-1e-6),b=display(t+1e-6);return {time:t,distance:Math.max(...a.points.slice(1).map((p,i)=>R.length(R.sub(p,b.points[i+1]))))};});
assert(joins.every(x=>x.distance<.002),'Handoff position discontinuity');assert(largestStep<.1,'Single-tick movement spike');assert(segment.carrier.landings.some(l=>/foot|ball/.test(l.bone)),'No foot landing');
const result={frames:rows.length,release,landing:segment.carrier.landings.map(l=>({time:l.time,bone:l.bone})),firstWallContact:{minimumKneeBend:Math.min(...contactBends),maximumKneeBend:Math.max(...contactBends),wallSupportRetained:true},largestStep,joins,modeRestore:true,reverseSeek:true};console.log(JSON.stringify(result,null,2));
fs.mkdirSync(new URL('../../Saved/Diagnostics/BodyflipFootIK/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/Diagnostics/BodyflipFootIK/verification.json',import.meta.url),JSON.stringify(result,null,2));

