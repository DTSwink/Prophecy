'use strict';
// Independent full-vs-lower forecast publication check. Full private upper
// predictions are intentionally not compared; every actual published bone is.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const P=require('./live-stair-planner.cjs'),K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js'),J=require('./live-join.cjs'),R=require('../../Labs/FootIKLab/recovery.js');
const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),data=JSON.parse(fs.readFileSync(path.join(folder,'nn-live-lower-forward-sequences.json')));
const clone=structuredClone,report={passed:false,cases:[],completePublishedFrames:0,materialPinFrames:0,maxPositionM:0,maxQuaternionComponent:0,maxFootReceiptNumber:0};
function difference(a,b,label){
 if(typeof a==='number'&&typeof b==='number'){assert(Number.isFinite(a)&&Number.isFinite(b),label+' finite');return Math.abs(a-b);}
 if(a===null||b===null||typeof a!=='object'||typeof b!=='object'){assert.deepEqual(a,b,label);return 0;}
 assert.deepEqual(Object.keys(a),Object.keys(b),label+' keys');let max=0;for(const k of Object.keys(a))max=Math.max(max,difference(a[k],b[k],label+'.'+k));return max;
}
function source(input,course,key){
 const rows=data.courses[course][key],poses=data.seeds.map(p=>({points:p.points.slice(1),axes:p.axes.slice(1)})),roots=data.seeds.map(p=>p.points[0]);
 for(const row of rows){roots.push(row.slice(0,3));poses.push({points:Array.from({length:25},(_,j)=>row.slice(3+j*3,6+j*3)),axes:Array.from({length:25},(_,j)=>Array.from({length:3},(_,i)=>row.slice(78+j*9+i*3,81+j*9+i*3)))});}
 const out={...input.source,names:data.names,fps:30,poses,roots,rootYawDegrees:data.courses[course].yaw.slice(0,poses.length),duration:(poses.length-1)/30,totalDuration:(poses.length-1)/30};out.directionMeta={...out.directionMeta,totalDuration:out.duration};return out;
}
async function check(name,course){
 const input=JSON.parse(fs.readFileSync(path.join(folder,name+'.input.json'))),sources=['full','lower'].map(key=>source(input,course,key)),runs=sources.map(s=>K.decode(s,input.parents)),terrain=T.create(input.settings),names=runs[0].names;
 const origin=runs[0].poses[0].points[0],end=Math.round(sources[0].duration*120),actual=tick=>{const p=K.at(runs[0],tick/120),height=terrain.rootHeight(p.points[0][2]-origin[2]);return {...clone(p),points:p.points.map(v=>[v[0]-origin[0],v[1]+height,v[2]-origin[2]])};};
 function window(which,from,to){const s=sources[which],next={...s,roots:s.roots.slice(from/4,to/4+1),poses:s.poses.slice(from/4,to/4+1),rootYawDegrees:s.rootYawDegrees.slice(from/4,to/4+1),duration:(to-from)/120,totalDuration:(to-from)/120};next.directionMeta={...next.directionMeta,totalDuration:next.duration};return {source:next,sourceStartTick:from};}
 const planners=sources.map((_,i)=>P.create({...input,...window(i,0,96),handoff:false,initialHistory:{previousTick:0,currentTick:4,previous:actual(0),current:actual(4)}}));
 for(const p of planners)assert((await p.plan()).ready);
 let accepted=4,compared=0,pins=0;const receipts=[];
 async function consume(to){
  for(let tick=accepted+1;tick<=to;tick++){
   const current=actual(tick),frames=planners.map(p=>p.frame(tick));assert(frames.every(Boolean),'prospective coverage');
   const joined=frames.map(candidate=>J.join({candidate,current,parents:input.parents,names}));
   const a=joined[0].frame,b=joined[1].frame;
   for(let j=0;j<26;j++){
    report.maxPositionM=Math.max(report.maxPositionM,R.length(R.sub(a.pose.points[j],b.pose.points[j])));
    for(let k=0;k<4;k++)report.maxQuaternionComponent=Math.max(report.maxQuaternionComponent,Math.abs(a.pose.q[j][k]-b.pose.q[j][k]));
   }
   report.maxFootReceiptNumber=Math.max(report.maxFootReceiptNumber,difference(a.feet,b.feet,name+' tick'+tick+' feet'));
   assert.deepEqual(a.root,b.root);assert.equal(a.pelvisOffset,b.pelvisOffset);assert.equal(a.influence,b.influence);
   // The same actually displayed receipt is supplied to both next solves,
   // including current raw game history and exact material contact IDs/pivots.
   a.rootHeading=K.rootHeading(runs[0],tick/120,input.settings);receipts.push({tick,frame:clone(a)});
   compared++;if(a.feet.some(f=>f.contact))pins++;
  }
  accepted=to;
 }
 await consume(64);
 for(const p of planners)p.accept(receipts);
 for(let i=0;i<2;i++)assert((await planners[i].plan(window(i,60,192))).ready);
 receipts.length=0;await consume(144);
 for(const p of planners)p.accept(receipts);
 const results=[];for(let i=0;i<2;i++)results.push(await planners[i].plan(window(i,140,end)));
 assert(results.every(x=>x.ready));assert.equal(results[0].continuity.safe,results[1].continuity.safe);assert.equal(results[0].continuity.pinShiftM,results[1].continuity.pinShiftM);
 receipts.length=0;await consume(end);
 for(const p of planners)p.cancel();report.completePublishedFrames+=compared;report.materialPinFrames+=pins;report.cases.push({name,course,frames:compared,pinnedFrames:pins,stopAndReverse:true,turning:true,actualHistoryAndReplans:2});
}
(async()=>{const start=performance.now(),cpu=process.cpuUsage();for(const [name,course] of [['walk-stairs',0],['run-down',1],['walk-uneven',0]])await check(name,course);report.passed=report.maxPositionM<=1e-8&&report.maxQuaternionComponent<=1e-10&&report.maxFootReceiptNumber<=1e-8;const used=process.cpuUsage(cpu);report.cpuMs=(used.user+used.system)/1000;report.wallMs=performance.now()-start;report.note='All 25 published bones plus synthetic root; original strict native pose/rotation gates, exact categorical contact semantics. Unused private upper forecast is not equivalent.';fs.writeFileSync(path.join(folder,'live-lower-publication.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));assert(report.passed,'Publication parity failed');assert(report.materialPinFrames>0,'No material contacts tested');})().catch(e=>{report.error=String(e);fs.writeFileSync(path.join(folder,'live-lower-publication.json'),JSON.stringify(report,null,2));console.error(e);process.exitCode=1;});
