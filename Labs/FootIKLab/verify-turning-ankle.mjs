import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),rig=read('data/rig.json'),data=read('snapshots/ankle-turn-source.json'),settings=read('snapshots/ankle-turn-settings.json');
const run=K.decode(data,rig.parents),before=JSON.stringify(run.poses),m=K.prepare(run,settings),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
let minUp=1,maxStep=0,maxMaterialError=0,contactStep=0;
for(let i=170;i<=202;i++){
 const f=m.frames[i],l=S.leg(f.pose,run.names,'L'),shoe=S.footFrame(f.pose,l.foot,l.toe,'L');
 minUp=Math.min(minUp,shoe.up[1]);
 const step=R.length(R.qlog(R.qm(f.pose.q[l.foot],R.qinv(m.frames[i-2].pose.q[l.foot]))))*180/Math.PI;
 maxStep=Math.max(maxStep,step);if(i===198)contactStep=step;
}
for(const f of m.frames)for(const foot of f.feet)if(foot.contact){
 const l=S.leg(f.pose,run.names,foot.side),point=R.add(f.pose.points[l.foot],R.rotate(f.pose.q[l.foot],foot.contact.localPoint));
 maxMaterialError=Math.max(maxMaterialError,R.length(R.sub(point,foot.contact.point)));
}
check('85-101 shoe stays upright instead of rolling sideways/upside-down',minUp>.75);
check('99 landing has no rotation snap',contactStep<2);
check('turn recovery spread across swing instead of last landing frames',maxStep<20);
check('material pins remain exact',maxMaterialError<1e-7);
check('complete shoe clearance and leg reach retained',m.metrics.maxPenetration<1e-5&&m.metrics.maxReachError<1e-6);
check('raw NN source unchanged',JSON.stringify(run.poses)===before);
const result={passed:true,checks,minUp,maxStep,contactStep,maxMaterialError,metrics:m.metrics};
fs.writeFileSync(new URL('turning-ankle-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
