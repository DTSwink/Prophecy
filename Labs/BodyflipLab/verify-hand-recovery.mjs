// Feasible leading-foot/hand fixture with actual body contacts.
// Current strength tiers; early hand marker leaves real contact travel.
// Independent body/arm recovery clocks; cached motions only, no UI/NN/service.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const fixture={"loadYMs":200,"loadFullMs":300,"ramps":false,"mode":"walk","motion":"kinematic","runSeconds":1,"runPhase":0,"attack":"slashLD","jumpEarly":0.1,"jumpBlend":0.4,"legBlend":0.2,"handBend":0.35,"loadMs":100,"rebound":0.5,"supportReach":0.99,"supportTrigger":0.05,"supportAlpha":1,"supportSpeed":800,"supportCone":30,"jumpSkew":0.5,"platforms":[{"id":"floor","position":[0,-0.2,-0.5599910537770252],"size":[3.6,0.4,66.20677485127891],"rotation":[0,0,0,1]},{"id":"left","position":[-2.163746750430836,2.07889393668845,10.880017892445949],"size":[6,0.12,18],"rotation":[0,0,-0.3826834323650897,0.9238795325112867]},{"id":"right","position":[2.163746750430836,2.07889393668845,10.880017892445949],"size":[6,0.12,18],"rotation":[0,0,0.3826834323650897,0.9238795325112867]}],"jumpEvents":[{"id":"first","time":0.9333333333333333,"surface":"floor","pushWith":"foot","jumpPercent":100,"attack":"none","attackDelay":0,"attackIn":0.2,"attackOut":0.25,"flip":90,"twist":0,"turnDelay":0,"turnDuration":0.8,"turnIn":0.4,"turnOut":0.4,"turnAxis":null,"pose":"none","poseIn":0.2,"poseHold":0.3,"poseOut":0.25},{"id":"mmvshzv0v_0","time":1.95,"surface":"auto","pushWith":"handBoth","jumpPercent":50,"attack":"none","attackDelay":0,"attackIn":0.2,"attackOut":0.25,"flip":0,"twist":0,"turnDelay":0,"turnDuration":0.8,"turnIn":0.4,"turnOut":0.4,"turnAxis":null,"pose":"none","poseIn":0.2,"poseHold":0.3,"poseOut":0.25}],"airFlip":false,"trimOut":2.55};
function bank(){
 const meta=read('data/walk-drawn-phases.json'),count=Math.ceil(5*meta.fps)+2,width=3+meta.names.length*12,b=Buffer.alloc(count*width*4),fd=fs.openSync(new URL('data/walk-drawn-phases.bin',import.meta.url),'r');try{assert.equal(fs.readSync(fd,b,0,b.length,0),b.length);}finally{fs.closeSync(fd);}
 const roots=[],poses=[];for(let f=0;f<count;f++){const row=Array.from({length:width},(_,i)=>b.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}return F.decodeNN({...meta,duration:5,roots,poses});
}

const run=bank(),reports=[];
const gap=(a,b)=>Math.max(...a.points.map((p,i)=>R.length(R.sub(R.sub(p,a.points[0]),R.sub(b.points[i],b.points[0])))));
const angle=(a,b)=>Math.max(...a.q.map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(b.q[i]))))));
for(const [hand,body,limb] of [['handBoth',.4,.2],['handBoth',.2,.4],['handBoth',.4,.4],['handBoth',.6,.1],['handBoth',.1,.6],['handBoth',0,.2],['handBoth',.4,0],['handL',.4,.2],['handR',.4,.2]]){
 const settings=C.sanitize({...fixture,jumpFoot:'L',jumpBlend:body,legBlend:limb,jumpEvents:fixture.jumpEvents.map((e,i)=>i?{...e,pushWith:hand}:e)});
 const sequence=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:3}),segment=sequence.segments.at(-1),release=segment.airStart;
 assert(Number.isFinite(release),hand+' releases');
 if(hand==='handBoth')assert(segment.support.paired,'Both fixture actually uses both arms');
 let largest=0,rotation=0;
 for(const duration of new Set([body,limb])){
  // A requested zero-duration blend may jump at release; other deadlines must not.
  if(!duration)continue;
  const t=release+duration,a=sequence.sample(t-1e-7).pose,b=sequence.sample(t+1e-7).pose;
  largest=Math.max(largest,gap(a,b));rotation=Math.max(rotation,angle(a,b));
  assert(gap(a,b)<1e-4,hand+' '+body+'/'+limb+' position continuity at '+duration);
  assert(angle(a,b)<1e-3,hand+' '+body+'/'+limb+' rotation continuity at '+duration);
 }
 // Scene playback, scrubbing and a fresh loop must agree across both deadlines.
 const times=[release,release+limb-.000123,release+limb+.000123,142/60,release+body+.000123];
 const frames=times.map(t=>JSON.stringify(sequence.sample(t)));
 for(let i=times.length-1;i>=0;i--)assert.equal(JSON.stringify(sequence.sample(times[i])),frames[i],'repeat/seek stability');
 reports.push({hand,body,limb,release,maxSeamMetres:largest,maxSeamRadians:rotation});
}
console.log(JSON.stringify({cases:reports.length,reports},null,2));
