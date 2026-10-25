import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),R=require('./recovery.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const checks=[],check=(name,ok)=>{assert(ok,name);checks.push(name);},rad=Math.PI/180;
const distance=(a,b)=>R.length(R.sub(a,b)),local=p=>R.localize(p.points,p.q,m.parents);
// The imported rig's flexion axis is -Z in the thigh frame. Measure actual
// segment directions, independently of the transition's reference normal.
function angle(p,side){const l=local(p),k=m.names.indexOf('calf_'+side),f=m.names.indexOf('foot_'+side),u=R.unit(l.p[k]),v=R.unit(R.rotate(l.q[k],l.p[f]));return Math.atan2(-R.cross(u,v)[2],R.dot(u,v));}
const floor={id:'floor',position:[0,-.2,-.5599910537770252],size:[3.6,.4,66.20677485127891],rotation:[0,0,0,1]};
const motions=new Map();
async function gait(name,phase=0){const key=name+phase;if(!motions.has(key)){const res=await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:name,duration:5,phase,drawn:true})});assert(res.ok);motions.set(key,F.decodeNN(await res.json()));}return motions.get(key);}
const measurements=[];
for(const options of [
 {mode:'walk'}, {mode:'jump'}, {mode:'walk',jumpFoot:'L'},
 {mode:'walk',legBlend:.05,jumpBlend:.4}, {mode:'walk',legBlend:.6,jumpBlend:.05},
 {mode:'jump',runPhase:.5,jumpFoot:'L'}, {mode:'walk',loadMs:0},
]){
 const s=C.sanitize({ramps:false,platforms:[floor],...options}),run=await gait(s.mode==='walk'?'walk':'run',s.runPhase),a=F.sequence(run,jumps,s,m.parents).segments[0],label=JSON.stringify(options);
 check('Fixture pushes '+label,Number.isFinite(a.airStart));
 const start=Math.min(a.jumpStart,a.airStart),end=Math.max(a.jumpStart+s.jumpBlend,a.airStart+s.legBlend)+.03;
 let min=Infinity,max=-Infinity,maxLengthError=0,minimumAt=0;
 // NN and imported clip lengths differ by about 2mm. Compare against those
 // actual source ranges, rather than treating their transition as stretching.
 const authored=[...run.poses,...jumps.flatMap(c=>c.poses)];
 const lengths=['l','r'].map(side=>['thigh','calf','foot'].map(n=>m.names.indexOf(n+'_'+side))).flatMap(ids=>[[ids[0],ids[1]],[ids[1],ids[2]]]).map(ids=>{const lengths=authored.map(p=>distance(p.points[ids[0]],p.points[ids[1]]));return {ids,min:Math.min(...lengths),max:Math.max(...lengths)};});
 for(let t=start;t<=end;t+=1/4000){const p=a.sample(t).pose;for(const side of ['l','r']){const b=angle(p,side);if(b<min){min=b;minimumAt=t;}max=Math.max(max,b);}
  for(const l of lengths){const value=distance(p.points[l.ids[0]],p.points[l.ids[1]]);maxLengthError=Math.max(maxLengthError,l.min-value,value-l.max);}
 }
 check('Neither knee bends backwards '+label,min>=-1e-4);
 check('Neither knee overfolds '+label,max<=150*rad+1e-4);
 check('Segment lengths stay within source-data range '+label,maxLengthError<.00005);
 const side=a.supportFoot.toLowerCase(),h=1e-6,bend=t=>angle(a.sample(t).pose,side);
 const rateBefore=(bend(a.airStart)-bend(a.airStart-h))/h,rateAfter=(bend(a.airStart+h)-bend(a.airStart))/h;
 check('Release has no angular velocity snap '+label,Math.abs(rateAfter-rateBefore)<.1);
 const finish=a.airStart+s.legBlend,left=(bend(finish)-bend(finish-h))/h,right=(bend(finish+h)-bend(finish))/h;
 check('Leg reaches moving target without a velocity snap '+label,Math.abs(right-left)<.05);
 const p=a.sample(finish).pose,target=a.animationLeg(finish,p).pose;
 check('Leg still meets its original animation deadline '+label,Math.abs(angle(p,side)-angle(target,side))<1e-9);
 const saved=JSON.stringify(a.sample(start+.04));a.sample(end);a.sample(0);
 check('Scrubbing remains deterministic '+label,JSON.stringify(a.sample(start+.04))===saved);
 measurements.push({options,minDegrees:min/rad,maxDegrees:max/rad,minimumAt,releaseVelocityError:Math.abs(rateAfter-rateBefore)});
 if(options.mode==='walk'&&Object.keys(options).length===1){
  check('Reported frame59 has a forward-bending support knee',angle(a.sample(59/60).pose,side)>20*rad&&angle(a.sample(59/60).pose,side)<45*rad);
  // No clamped straight-leg plateau: a single smooth turnaround, then the
  // knee keeps bending toward the moving target rather than locking/recoiling.
  let reversals=0,previous=0,maxFrameChange=0;
  for(let t=a.airStart+1/6000;t<finish;t+=1/6000){const v=(bend(t+1e-6)-bend(t-1e-6))/2e-6;if(v*previous<0)reversals++;if(Math.abs(v)>.01)previous=v;}
  for(let frame=57;frame<68;frame++)maxFrameChange=Math.max(maxFrameChange,Math.abs(bend((frame+1)/60)-bend(frame/60))/rad);
  check('No knee bounce or straight-leg lock',reversals===1&&min>rad);
  check('No frame-sized knee pop after braking',maxFrameChange<16);
  // Compare against the previous unconstrained blend without touching saved
  // settings. Contact timing, pins and the authored root must remain exact.
  const register=C.registerRig;C.registerRig=()=>{};let old;
  try{old=F.sequence(run,jumps,s,[...m.parents]).segments[0];}finally{C.registerRig=register;}
  check('Previous implementation reproduces the reported backwards knee',angle(old.sample(59/60).pose,side)<-70*rad);
  check('Push and release timing unchanged',old.jumpStart===a.jumpStart&&old.airStart===a.airStart);
  let rootError=0,pinError=0;
  for(let t=a.supportStart;t<end;t+=1/480){const before=old.sample(t),after=a.sample(t);rootError=Math.max(rootError,distance(before.root,after.root));if(t<=a.airStart)pinError=Math.max(pinError,distance(before.pose.points[a.support.leg.foot],after.pose.points[a.support.leg.foot]));}
  check('Root motion and pinned foot unchanged',rootError<1e-10&&pinError<1e-10);
 }
}
// Both moving entry and return paths of every existing attack family.
let attackMin=Infinity,attackMax=-Infinity;
for(const family of m.clips){const meta=family.variants[0],bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),clip=C.decode(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),m.names,m.parents),idle=C.poseFromShared(m);let min=Infinity,max=-Infinity;
 for(const [begin,end] of [[0,.15],[.15+clip.duration,.6+clip.duration]])for(let t=begin;t<=end;t+=1/960){const p=C.sample(clip,t,idle,m.parents);for(const side of ['l','r']){const b=angle(p,side);min=Math.min(min,b);max=Math.max(max,b);}}
 check('Attack blends respect knee range '+family.name,min>=-1e-4&&max<=150*rad+1e-4);attackMin=Math.min(attackMin,min);attackMax=Math.max(attackMax,max);
}
const result={passed:checks.length,measurements,attackMinDegrees:attackMin/rad,attackMaxDegrees:attackMax/rad};
fs.writeFileSync(new URL('knee-blend-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
