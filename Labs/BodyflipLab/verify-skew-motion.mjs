import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),checks=[],measurements=[];
const check=(name,value)=>{assert(value,name);checks.push(name);};
const m=read('data/manifest.json'),run=F.decodeNN(read('data/roll-check.json')),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const pose=F.at(run,.5,m.parents),leg=S.leg(pose,run.names,'R'),pelvis=run.names.indexOf('pelvis');
function make(normal,velocity,skew){
 const contact=R.add(pose.points[leg.foot],S.lowestOffset(pose,leg,normal)),u=R.unit(R.cross(normal,[0,0,1])),v=R.cross(u,normal),surface=S.rectangle('test',contact,u,v,[-3,3,-3,3]);
 return F.create(run,jumps,C.sanitize({...read('roll-settings.json'),loadMs:0,jumpFoot:'R',jumpSkew:skew}),m.parents,pose,{time:0,surface,poseAt:()=>pose,velocityAt:()=>velocity,speed:Math.hypot(velocity[0],velocity[2])});
}
const delta=(jump,t,point=null)=>{const a=jump.sample(jump.jumpStart),b=jump.sample(jump.jumpStart+t);return R.sub(point===null?b.root:b.pose.points[point],point===null?a.root:a.pose.points[point]);};
for(const velocity of [[0,-4,3],[0,4,3],[1,-4,3],[0,0,0]]){

 for(const normal of [R.unit([1,1,0]),R.unit([-1,1,0]),[1,0,0]]){
  const carry=F.carryVelocity(velocity,normal,[0,1,0]),flat=make([0,1,0],carry,1),jump=make(normal,velocity,1),tag=normal+'/'+velocity;
  check('Contact succeeds '+tag,Number.isFinite(jump.jumpStart));
  for(const t of [.1,.3,flat.apex+.2]){
   check('100 percent root matches flat after contact cancellation '+tag+'/'+t,R.length(R.sub(delta(jump,t),delta(flat,t)))<1e-8);
   check('100 percent pelvis matches flat after contact cancellation '+tag+'/'+t,R.length(R.sub(delta(jump,t,pelvis),delta(flat,t,pelvis)))<1e-8);
  }
  check('Common tangential momentum retained '+tag,Math.abs(delta(jump,.1)[0]-carry[0]*.1)<1e-9&&Math.abs(delta(jump,.1)[2]-carry[2]*.1)<1e-9);
  measurements.push({normal,velocity,rootDeltaAtPointOne:delta(jump,.1),flatDeltaAtPointOne:delta(flat,.1)});
 }
}
for(const skew of [0,.5,1]){
 const normal=R.unit([1,1,0]),velocity=[0,-4,3],jump=make(normal,velocity,skew),rest=make(normal,[0,0,0],skew),direction=F.jumpDirection(normal,skew),t=.1;
 const tangent=F.carryVelocity(velocity,normal,direction);
 check('No carried surface-normal or push-axis component '+skew,Math.abs(R.dot(tangent,normal))<1e-9&&Math.abs(R.dot(tangent,direction))<1e-9);
 check('Incoming motion uses effective push plane '+skew,R.length(R.sub(R.sub(delta(jump,t),delta(rest,t)),R.mul(tangent,t)))<1e-8);
 check('Debug arrow matches launch axis '+skew,R.length(R.sub(jump.pushDebug(jump.jumpStart).direction,direction))<1e-9);
}
fs.writeFileSync(new URL('skew-motion-verification.json',import.meta.url),JSON.stringify({passed:true,browserVisualVerified:false,checks,measurements},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,example:measurements[0]}));
