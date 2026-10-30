// Bounded offline audit of grounded hand preparation. No worker or browser.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),H=require('./hand-support.js'),F=require('./flight.js'),I=require('./idle.js'),T=require('./torso.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const motions={idle:I.create(read('data/idle.json'),bytes('data/idle.bin'),manifest).motion(),walk:F.decodeNN(read('data/walk-default.json')),run:F.decodeNN(read('data/run-default.json'))};
const {add,sub,mul,dot,length}=R,id=n=>names.indexOf(n),floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,20],.4),torso=T.create(names,parents,reference),distance=(a,b)=>length(sub(a,b));
const specs=['l','r'].flatMap(side=>[['upperarm','lowerarm',.058],['lowerarm','hand',.048],['thigh','calf',.083],['calf','foot',.062]].map(([a,b,r])=>({name:a+'_'+side,a:id(a+'_'+side),b:id(b+'_'+side),r})));
function pointSegment(p,a,b){const v=sub(b,a),t=Math.max(0,Math.min(1,dot(sub(p,a),v)/dot(v,v)));return distance(p,add(a,mul(v,t)));}
function minimum(f){let lo=0,hi=1;for(let i=0;i<20;i++){const a=lo+(hi-lo)/3,b=hi-(hi-lo)/3;if(f(a)<f(b))hi=b;else lo=a;}return Math.min(f(0),f(1),f((lo+hi)/2));}
function pointBox(p,b){const v=sub(p,b.center);return Math.hypot(...[b.forward,b.side,b.up].map((axis,i)=>Math.max(0,Math.abs(dot(v,axis))-b.dims[i]/2)));}
function clearances(p){
 let ground=Infinity,self=Infinity,selfPair='';const record=(gap,pair)=>{if(gap<self){self=gap;selfPair=pair;}};
 const boxes=torso.map(s=>T.world(p,s));
 for(const a of specs){
  ground=Math.min(ground,p.points[a.a][1]-a.r,p.points[a.b][1]-a.r);
  for(const b of boxes){if(a.name.startsWith('upperarm')&&['spine_04','spine_05'].includes(b.name))continue;record(minimum(t=>pointBox(add(p.points[a.a],mul(sub(p.points[a.b],p.points[a.a]),t)),b))-a.r,a.name+'/'+b.name);}
 }
 for(const a of specs.filter(a=>a.name.startsWith('lowerarm')))for(const b of specs.filter(a=>a.name.startsWith('thigh')||a.name.startsWith('calf'))){record(minimum(t=>pointSegment(add(p.points[a.a],mul(sub(p.points[a.b],p.points[a.a]),t)),p.points[b.a],p.points[b.b]))-a.r-b.r,a.name+'/'+b.name);}
 for(const b of boxes)ground=Math.min(ground,b.center[1]-[b.forward,b.side,b.up].reduce((v,axis,i)=>v+Math.abs(axis[1])*b.dims[i]/2,0));
 for(const side of ['L','R']){const leg=S.leg(p,names,side);ground=Math.min(ground,...S.footPoints(p,leg.foot,leg.toe,side).map(v=>p.points[leg.foot][1]+v[1]));const hand=id('hand_'+side.toLowerCase());ground=Math.min(ground,...H.corners(p,hand,side).map(v=>p.points[hand][1]+v[1]));}
 const neck=p.points[id('neck_02')],head=add(neck,mul(p.axes[id('head')][0],Math.max(.054,distance(neck,p.points[id('head')]))));ground=Math.min(ground,neck[1]-.1,head[1]-.1);
 return {ground,self,selfPair};
}
const reports=[];
for(const gait of ['idle','walk','run'])for(const side of ['L','R']){
 const time=gait==='run'?.4:.1,settings=C.sanitize({mode:gait==='run'?'jump':gait,motion:'kinematic',ramps:false,surfaceIK:false,supportAlpha:0,platforms:[S.platformRecord(floor)],jumpEvents:[{id:'hand',time,pushWith:'hand'+side}]}),sequence=F.sequence(motions[gait],jumps,settings,parents,reference,null,null,{horizon:1.4}),segment=sequence.segments[0];
 const report={gait,side,status:sequence.events[0].status,contact:segment.contactTime,release:segment.airStart,ground:Infinity,self:Infinity,pin:0,kneeSpeed:0,seam:0,seamRotation:0};
 const end=Number.isFinite(segment.airStart)?segment.airStart+.3:time+.6;let previous=null;
 for(let t=time;t<=end;t+=1/240){
  const frame=sequence.sample(t),p=frame.pose;assert(p.points.flat().every(Number.isFinite)&&p.q.flat().every(Number.isFinite),`${gait} ${side} finite`);
  if(frame.supportState==='PIN'){const pin=segment.contactMotion.sample(t-segment.contactTime).foot;report.pin=Math.max(report.pin,distance(p.points[segment.supportBone],pin));}
  if(previous)for(const side of ['l','r']){const knee=id('calf_'+side),hip=id('thigh_'+side),speed=distance(sub(p.points[knee],p.points[hip]),sub(previous.points[knee],previous.points[hip]))*240;if(speed>report.kneeSpeed){report.kneeSpeed=speed;report.kneeSpeedTime=t;report.kneeSpeedSide=side;report.kneeSpeedPhase=frame.phase;}}
  if(Math.round((t-time)*240)%2===0){const gaps=clearances(p);report.ground=Math.min(report.ground,gaps.ground);if(gaps.self<report.self){report.self=gaps.self;report.selfPair=gaps.selfPair;report.selfTime=t;}}
  previous=p;
 }
 for(const t of [time,segment.contactTime,segment.jumpStart,segment.airStart])if(Number.isFinite(t)){const a=sequence.sample(t-1e-7).pose,b=sequence.sample(t+1e-7).pose;report.seam=Math.max(report.seam,...a.points.slice(1).map((v,i)=>distance(v,b.points[i+1])));report.seamRotation=Math.max(report.seamRotation,...a.q.slice(1).map((q,i)=>length(R.qlog(R.qm(q,R.qinv(b.q[i+1]))))));}
 reports.push(report);
}
console.log(JSON.stringify(reports,null,2));
for(const r of reports){
 const label=`${r.gait} ${r.side}`;
 assert.equal(r.status,'Push',label+' reaches a hand push');
 assert(r.pin<2e-5,label+' wrist remains pinned');
 assert(r.seam<.001,label+' continuous joins');
 assert(r.seamRotation<.003,label+' continuous bone orientation at joins');
 // One millimetre allows the rig shells/contact fit numerical overlap; the
 // original failure crossed the floor and other limbs by centimetres.
 assert(r.ground>=-.001,label+' no body or knee passes through the floor');
 assert(r.self>=-.001,label+' torso and arm/leg clearance');
 assert(r.kneeSpeed<6,label+' no rapid knee fold/unfold during preparation');
}
