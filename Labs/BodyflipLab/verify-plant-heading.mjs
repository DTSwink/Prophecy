import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),m=read('data/manifest.json'),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);},dist=(a,b)=>R.length(R.sub(a,b));
const run=F.decodeNN(await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:.61,drawn:true})})).json());
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const settings=C.sanitize({supportCone:60,supportAlpha:6,supportSpeed:400,footRollSpeed:400,jumpEvents:[{id:'first',time:53/60,surface:'floor'},{id:'second',time:115/60,surface:'auto'},{id:'third',time:146/60,surface:'auto'}]});
const pose=F.at(run,.9,m.parents),forward=(p,n)=>{const f=R.rotate(p.q[1],[0,-1,0]),h=R.unit([f[0],0,f[2]]);return R.unit(R.sub(h,R.mul(n,R.dot(h,n))));};
const tangent=(v,n)=>R.unit(R.sub(v,R.mul(n,R.dot(v,n))));
const oriented=(p,l)=>{const q=p.q.slice(),points=p.points.slice();q[l.foot]=l.plant.footQ;q[l.toe]=l.plant.toeQ;points[l.toe]=R.add(points[l.foot],R.rotate(q[l.foot],l.toeLocal));return {points,q,axes:q.map(R.toAxes)};};
for(const surface of S.terrain(5))for(const side of ['L','R'])for(const yaw of [0,.7,-1.2]){
 const turn=R.qexp([0,yaw,0]),p={points:pose.points.map(v=>R.rotate(turn,v)),q:pose.q.map(q=>R.qm(turn,q))};p.axes=p.q.map(R.toAxes);
 const plan=S.plan(p,run.names,m.parents,{...settings,jumpFoot:side},surface,0,()=>p),l=plan.leg,shoe=S.footFrame(oriented(p,l),l.foot,l.toe,side);
 check('Plant faces body heading on '+surface.id+'/'+side+'/'+yaw,dist(tangent(shoe.forward,surface.normal),forward(p,surface.normal))<1e-8);
 check('Plant retains requested pitch '+surface.id+'/'+side+'/'+yaw,Math.abs(R.dot(shoe.forward,surface.normal)+Math.sin(settings.plantPitch*Math.PI/180))<1e-8);
 // Jump root basis can equal pelvis basis; it must never redefine shoe heading.
 const changed={...p,q:p.q.map(q=>q.slice())};changed.q[0]=p.q[1];changed.axes=changed.q.map(R.toAxes);
 const other=S.plan(changed,run.names,m.parents,{...settings,jumpFoot:side},surface,0,()=>changed).leg;
 check('Imported root basis cannot yaw plant '+surface.id+'/'+side+'/'+yaw,Math.abs(R.dot(other.plant.footQ,l.plant.footQ))>1-1e-9);
}
const seq=F.sequence(run,jumps,settings,m.parents),third=seq.segments[2],l=third.support.leg,p=third.support.terminal.pose,expected=forward(p,third.surface.normal),f=S.footFrame(p,l.foot,l.toe,l.side),angle=Math.acos(Math.max(-1,Math.min(1,R.dot(tangent(f.forward,third.surface.normal),expected))))*180/Math.PI;
check('Saved jump3 captures successfully',Number.isFinite(third.jumpStart));
check('Saved jump3 captured shoe faces forward within five degrees',angle<5);
const during=third.sample(third.jumpStart+Math.min(.02,third.release/2)).pose,roll=S.footFrame(during,l.foot,l.toe,l.side);
check('Heel-to-toe roll stays forward',R.dot(tangent(roll.forward,third.surface.normal),expected)>.99);
const near=third.sample(151/60).pose,nearFoot=S.footFrame(near,l.foot,l.toe,l.side);
check('Saved frame151 shoe already faces forward',R.dot(tangent(nearFoot.forward,third.surface.normal),expected)>.99);
const result={passed:true,browserVisualVerified:false,checks,third:{side:l.side,pushTime:third.jumpStart,captureYawErrorDegrees:angle,footForward:f.forward,expectedForward:expected,incoming:third.incomingVelocity,carried:third.carriedVelocity}};
fs.writeFileSync(new URL('plant-heading-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({...result,checks:checks.length}));
