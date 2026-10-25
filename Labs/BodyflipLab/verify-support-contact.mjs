import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),checks=[],measurements=[];
const check=(name,value)=>{assert(value,name);checks.push(name);},dist=(a,b)=>R.length(R.sub(a,b));
const m=read('data/manifest.json'),run=F.decodeNN(read('data/roll-check.json')),pose=F.at(run,.5,m.parents),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const renderSource=fs.readFileSync(new URL('renderer.js',import.meta.url),'utf8'),Renderer=vm.runInNewContext(renderSource+';WebGLMotionRenderer;', {BodyflipSupport:S,posAt:(p,i)=>p.points[i],add:R.add,mul:R.mul});
for(const side of ['L','R'])for(const degrees of [0,100,180,260]){
 const q=R.qexp([0,0,degrees*Math.PI/180]),p={points:pose.points.map(v=>R.rotate(q,v)),q:pose.q.map(v=>R.qm(q,v))};p.axes=p.q.map(R.toAxes);
 const l=S.leg(p,run.names,side),base=S.leg(pose,run.names,side),f=S.footFrame(p,l.foot,l.toe,side),original=S.footFrame(pose,l.foot,l.toe,side);
 check('Anatomical up rotates continuously '+side+'/'+degrees,dist(f.up,R.rotate(q,original.up))<1e-9);
 const points=S.footPoints(p,l.foot,l.toe,side),before=S.footPoints(pose,base.foot,base.toe,side);
 check('Foot geometry covariant '+side+'/'+degrees,points.every((v,i)=>dist(v,R.rotate(q,before[i]))<1e-9));
 const boxes=Renderer.prototype.footBoxes.call({},p,{ankle:l.foot,toe:l.toe,side:side==='L'?0:1});
 const corners=Object.values(boxes).flatMap(b=>[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>R.sub(R.add(b.center,R.add(R.mul(b.forward,x*b.dims[0]/2),R.add(R.mul(b.side,y*b.dims[1]/2),R.mul(b.up,z*b.dims[2]/2)))),p.points[l.foot])))));
 check('Rendered foot matches queried corners '+side+'/'+degrees,points.every(p=>corners.some(v=>dist(v,p)<1e-9)));
}
for(const side of ['L','R']){
 const p={points:pose.points.map(v=>v.slice()),q:pose.q.map(v=>v.slice()),axes:pose.axes.map(v=>v.map(a=>a.slice()))},l=S.leg(p,run.names,side),flip=R.qexp(R.mul(S.footFrame(p,l.foot,l.toe,side).forward,Math.PI));
 for(const i of [l.foot,l.toe]){p.q[i]=R.qm(flip,p.q[i]);p.axes[i]=R.toAxes(p.q[i]);}
 p.points[l.toe]=R.add(p.points[l.foot],R.rotate(flip,R.sub(pose.points[l.toe],pose.points[l.foot])));
 const contact=R.add(p.points[l.foot],S.lowestOffset(p,l,[0,1,0])),surface=S.rectangle('floor',contact,[1,0,0],[0,0,1],[-3,3,-3,3]);
 const plan=S.plan(p,run.names,m.parents,C.sanitize({jumpFoot:side,supportAlpha:0,supportReach:1}),surface,0,()=>p);
 check('Inverted foot can capture nearby ground '+side,Number.isFinite(plan.jumpDelay));
 check('Capture uses sole-facing orientation '+side,R.dot(S.footFrame(plan.terminal.pose,l.foot,l.toe,side).up,surface.normal)>0);
}
const state=await(await fetch('http://127.0.0.1:8876/state')).json(),settings=state.settings;
const raw=await(await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:settings.mode==='walk'?'walk':'run',duration:5,phase:settings.runPhase,drawn:settings.attack==='pike'||settings.attack.startsWith('slash')})})).json();
const sequence=F.sequence(F.decodeNN(raw),jumps,settings,m.parents);
for(const s of sequence.segments){if(!Number.isFinite(s.jumpStart))continue;
 const foot=s.support.leg,normal=s.surface.normal,up=S.footFrame(s.support.terminal.pose,foot.foot,foot.toe,foot.side).up;
 check('Saved setup plant faces surface '+s.supportStart,R.dot(up,normal)>0);
 check('Saved setup cancels incoming surface-normal motion '+s.supportStart,Math.abs(R.dot(s.carriedVelocity,normal))<1e-9);
 check('Saved setup cancels incoming push-axis motion '+s.supportStart,Math.abs(R.dot(s.carriedVelocity,s.direction))<1e-9);
 measurements.push({time:s.supportStart,push:s.jumpStart,side:foot.side,soleUpDot:R.dot(up,normal),normal,incoming:s.incomingVelocity,carried:s.carriedVelocity});
}
// Isolate the foot regression using the previous momentum rule: same third
// contact that was inverted, without moving its approach via the velocity fix.
const legacySource=fs.readFileSync(new URL('flight.js',import.meta.url),'utf8').replace('carryVelocity(incoming,surface.normal,direction)','sub(incoming,mul(direction,R.dot(incoming,direction)))');
const legacyContext={module:{exports:{}},require};vm.runInNewContext(legacySource,legacyContext);
const legacy=legacyContext.module.exports.sequence(F.decodeNN(raw),jumps,settings,m.parents);
for(const s of legacy.segments){if(!Number.isFinite(s.jumpStart))continue;
 const l=s.support.leg;
 check('Isolated foot fix plants sole first '+s.supportStart,R.dot(S.footFrame(s.support.terminal.pose,l.foot,l.toe,l.side).up,s.surface.normal)>0);
}
fs.writeFileSync(new URL('support-contact-verification.json',import.meta.url),JSON.stringify({passed:true,browserVisualVerified:false,checks,measurements,events:sequence.events},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
