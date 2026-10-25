import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);},dist=(a,b)=>R.length(R.sub(a,b));
// Frozen reproduction of the user's jump 3; /run only reads the precomputed phase bank.
const m=read('data/manifest.json'),settings=C.sanitize({runPhase:.61,supportCone:60,supportAlpha:7,supportSpeed:500,footRollSpeed:400,flipAngle:88,jumpEvents:[{id:'first',time:53/60,surface:'floor'},{id:'second',time:115/60,surface:'auto'},{id:'third',time:146/60,surface:'auto'}]});
const response=await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:.61,drawn:true})});
if(!response.ok)throw Error('Cached gait unavailable');const run=F.decodeNN(await response.json());
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),seq=F.sequence(run,jumps,settings,m.parents),time=149/60;
const pose=F.at(run,.5,m.parents),legs=['L','R'].map(side=>S.leg(pose,run.names,side));
for(const surface of S.terrain(4))for(const velocity of [[0,0,5],[-2,-4,5],[3,2,-1]]){
 const targetAt=alpha=>S.ideal(pose,legs,surface,velocity,{...settings,supportAlpha:alpha});
 const a=targetAt(0),b=targetAt(1),c=targetAt(7),tangent=R.sub(velocity,R.mul(surface.normal,R.dot(velocity,surface.normal)));
 check('Zero alpha below pelvis '+surface.id+'/'+velocity,a.every(v=>dist(v.raw,v.requested)<1e-10));
 check('Lead follows surface velocity '+surface.id+'/'+velocity,b.every(v=>dist(v.shift,R.mul(tangent,1/200))<1e-10));
 check('Lead linear and tangent '+surface.id+'/'+velocity,c.every(v=>dist(v.shift,R.mul(b[0].shift,7))<1e-10&&Math.abs(R.dot(v.shift,surface.normal))<1e-10));
 const turned={...pose,q:pose.q.map(q=>q.slice())};turned.q[0]=R.qexp([0,1.4,0]);
 check('Root facing cannot redirect world velocity '+surface.id+'/'+velocity,S.ideal(turned,legs,surface,velocity,settings).every(v=>dist(v.shift,c[0].shift)<1e-10));
}
const plane=p=>R.unit(R.cross(R.sub(p.points[2],p.points[0]),R.sub(p.points[1],p.points[0])));
const legPlane=(p,l)=>plane({points:[p.points[l.hip],p.points[l.knee],p.points[l.foot]]});
function hingeCheck(p,l){const expectedHip=R.rotate(R.qinv(l.hipQ),l.normal),expectedKnee=R.rotate(R.qinv(l.kneeQ),l.normal),actual=legPlane(p,l);return dist(R.rotate(p.q[l.hip],expectedHip),actual)<1e-7&&dist(R.rotate(p.q[l.knee],expectedKnee),actual)<1e-7;}
for(const l of legs){
 const same=S.solve(pose,l,pose.points[l.foot],m.parents);
 check('Unchanged target preserves pose '+l.side,[l.hip,l.knee,l.foot,l.toe].every(i=>dist(same.points[i],pose.points[i])<1e-8&&Math.abs(R.dot(same.q[i],pose.q[i]))>1-1e-8));
 const targets=[-.03,-.01,0,.01,.03].map(a=>R.add(pose.points[l.hip],R.mul(R.unit(R.add(l.upperAxis,R.mul(l.pole,a))),l.reach*.8)));
 const solved=targets.map(t=>S.solve(pose,l,t,m.parents));
 check('No pole flip through old singularity '+l.side,solved.slice(1).every((p,i)=>R.dot(legPlane(p,l),legPlane(solved[i],l))>.999));
 check('Knee remains a hinge '+l.side,solved.every(p=>hingeCheck(p,l)));
 check('Reach and bone lengths '+l.side,solved.every((p,i)=>dist(p.points[l.foot],targets[i])<1e-8&&Math.abs(dist(p.points[l.hip],p.points[l.knee])-l.upper)<1e-8&&Math.abs(dist(p.points[l.knee],p.points[l.foot])-l.lower)<1e-8));
 const q=R.qexp([.7,-.9,1.2]),rotated={points:pose.points.map(v=>R.rotate(q,v)),q:pose.q.map(v=>R.qm(q,v))};rotated.axes=rotated.q.map(R.toAxes);
 const transformed=S.solve(rotated,l,R.rotate(q,targets[1]),m.parents,1,{footQ:R.qm(q,l.footQ),toeQ:R.qm(q,l.toeQ)});
 check('Pole follows pelvis orientation '+l.side,transformed.points.every((p,i)=>dist(p,R.rotate(q,solved[1].points[i]))<1e-8));
}
for(const seg of seq.segments){const l=seg.support.leg;
 check('Saved sequence has successful plant '+seg.supportStart,Number.isFinite(seg.jumpStart));
 const times=[seg.supportStart,Math.min(time,seg.jumpStart),seg.jumpStart,seg.jumpStart+seg.release*.5,seg.jumpStart+seg.release];
 check('Saved support and pin use common hinge '+seg.supportStart,times.every(t=>hingeCheck(seg.sample(Math.max(t,seg.supportStart)).pose,l)));
 const debug=seg.idealDebug(seg.supportStart),other=debug.targets.find(t=>!t.selected);
 check('Other ideal is opposite selected foot '+seg.supportStart,other.foot!==l.side);
 check('Ideal markers match selection candidates '+seg.supportStart,debug.targets.every((t,i)=>dist(t.point,seg.supportScores[i].surface)<1e-8));
 check('Ideal markers finite and on platform '+seg.supportStart,debug.targets.every(t=>t.point.every(Number.isFinite)&&dist(seg.surface.closest(t.point),t.point)<1e-8));
 check('Captured markers stop following flight '+seg.supportStart,seg.idealDebug(seg.jumpStart+.5).targets.every((t,i)=>dist(t.point,seg.idealDebug(seg.jumpStart).targets[i].point)<1e-8));
}
const third=seq.segments[2];
check('Corrected saved third jump chooses closest score',third.supportFoot==='R'&&third.supportScores[1].distance<third.supportScores[0].distance);
const app=fs.readFileSync(new URL('app.js',import.meta.url),'utf8'),nodes={},context={$:id=>nodes[id]||=( {textContent:'',value:''}),renderer:{draw(){}},currentPose:pose,settings,physics:{com:()=>[0,0,0]},platformEditor:null,names:run.names,nameToIndex:new Map(run.names.map((n,i)=>[n,i])),playing:true,lastHUD:0,performance:{now:()=>50},simTime:time,attackTime:-1};
vm.createContext(context);vm.runInContext(app.slice(app.indexOf('function syncPlaybackReadout('),app.indexOf('function syncTarget(')),context);vm.runInContext('drawAll()',context);
check('Frame counter updates even when HUD throttled',nodes.frameRead.textContent==='F 149');
check('Timeline advances even when HUD throttled',nodes.scrub.value===time);
vm.runInContext('syncPlaybackReadout(150/60)',context);check('Next 60Hz step increments frame',nodes.frameRead.textContent==='F 150');
vm.runInContext('syncPlaybackReadout(86/60)',context);check('Reverse seek updates frame',nodes.frameRead.textContent==='F 86');
const rings=[],debugContext={flight:seq,simTime:time,add:R.add,mul:R.mul,ring:(...args)=>rings.push(args)};vm.runInNewContext(app.slice(app.indexOf('   const ideals=flight.idealDebug'),app.indexOf('   // Sparse world-height ticks')),debugContext);
check('Actual draw code renders red alternative ring',rings.length===1&&dist(rings[0][4],[1,.22,.2])<1e-9);
check('Ring uses other foot ideal',dist(rings[0][0],R.add(seq.idealDebug(time).targets.find(t=>!t.selected).point,R.mul(third.surface.normal,.012)))<1e-9);
const result={passed:true,browserVisualVerified:false,checks,frame:Math.round(time*60),third:{foot:third.supportFoot,scores:third.supportScores.map(s=>({foot:s.foot,distance:s.distance,shift:s.shift})),pushTime:third.jumpStart},events:seq.events};
fs.writeFileSync(new URL('target-knee-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({...result,checks:checks.length}));
