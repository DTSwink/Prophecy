'use strict';
// Native-policy fixture replays only. Runs sequentially without loading an NN.
const fs=require('node:fs'),path=require('node:path'),z=require('node:zlib'),crypto=require('node:crypto');
const V=require('./verify-slide-directions.cjs'),R=require('./recovery.js');
const DIR=path.resolve(__dirname,'../../Saved/FootIKSlideAudit20261029'),OUT=path.join(DIR,'heading');
const sourceHashes=Object.fromEntries(['surface.js','slide-entry.js','slide-arms.js'].map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname,name))).digest('hex')]));
const read=name=>JSON.parse(z.gunzipSync(fs.readFileSync(path.join(DIR,name+'.fixture.json.gz'))));
const DEG=180/Math.PI,clamp=v=>Math.max(-1,Math.min(1,v)),wrapped=a=>Math.atan2(Math.sin(a),Math.cos(a));
const cases=[
 ['run-forward','final-run-forward'],['run-backward','run-backward'],['run-left','final-run-left'],['run-right','run-right'],
 ['walk-forward','walk-forward'],['walk-backward','walk-backward-drop'],['walk-left','walk-left'],['walk-right','walk-right'],
 ['turn-positive','final-run-forward-yaw120',true],['turn-negative','final-run-forward-yaw-120',true],['current','final-current'],
 ['walk-forward-82','walk-forward-82'],['run-backward-85','run-backward-85'],['parallel-forward','parallel-run-forward'],['parallel-turn','parallel-turn',true],['floor-deletion','floor-deletes-during-entry']
];
function headingChecks(result,base,name,turning){
 const frames=result.model.frames,names=result.run.names,pelvis=names.indexOf('pelvis'),report={name,slideTicks:0,settledTicks:0,commandSweepDeg:0,actualSweepDeg:0,maxHeadingErrorDeg:0,maxHeadingStepDeg:0,maxCommandStepDeg:0,maxSoleGapM:0,maxPalmGapM:0,maxHandStepM:0,handSwitches:[],samples:[],failures:[]};
 let prev=null,first=null,last=null;
 report.footReach={L:{samples:0,contacts:0,sumGapM:0,maxGapM:0},R:{samples:0,contacts:0,sumGapM:0,maxGapM:0}};
 const yaw=v=>Math.atan2(v[0],v[2]);
 for(let i=0;i<frames.length;i++){
  const f=frames[i],slide=f.slide;if(!slide){prev=null;continue;}report.slideTicks++;
  const actual=slide.heading||R.rotate(f.pose.q[pelvis],[0,-1,0]),command=slide.commandedHeading;
  if(!command||!command.every(Number.isFinite)||Math.abs(R.length(command)-1)>.00001){if(!report.failures.includes('missing/invalid commanded heading'))report.failures.push('missing/invalid commanded heading');continue;}
  const normal=f.surface.normal,ay=yaw(actual),cy=yaw(command),fully=(slide.blend===1&&(slide.legBlend??1)===1&&(slide.pelvisBlend??1)===1),error=Math.abs(wrapped(ay-cy))*DEG;
  const hands=slide.hands||[slide.hand].filter(Boolean);
  let closest=null;
  for(const hand of hands){if(hand.touching){report.maxPalmGapM=Math.max(report.maxPalmGapM,Math.abs(hand.gap));closest=hand.side;}}
  for(const foot of f.feet)if(foot.slideContact)report.maxSoleGapM=Math.max(report.maxSoleGapM,Math.abs(foot.soleGap));
  if(fully){report.settledTicks++;report.maxHeadingErrorDeg=Math.max(report.maxHeadingErrorDeg,error);
   for(const foot of f.feet){const reach=report.footReach[foot.side];if(!reach)continue;const gap=Math.max(0,foot.soleGap??0);reach.samples++;reach.contacts+=gap<.012?1:0;reach.sumGapM+=gap;reach.maxGapM=Math.max(reach.maxGapM,gap);}}
  if(prev){const da=wrapped(ay-prev.ay)*DEG,dc=wrapped(cy-prev.cy)*DEG;report.actualSweepDeg+=da;report.commandSweepDeg+=dc;report.maxHeadingStepDeg=Math.max(report.maxHeadingStepDeg,Math.abs(da));report.maxCommandStepDeg=Math.max(report.maxCommandStepDeg,Math.abs(dc));
   for(const side of ['l','r']){const j=names.indexOf('hand_'+side),a=R.sub(f.pose.points[j],f.pose.points[pelvis]),b=R.sub(prev.f.pose.points[j],prev.f.pose.points[pelvis]);report.maxHandStepM=Math.max(report.maxHandStepM,R.length(R.sub(a,b)));}
   if(closest&&prev.closest&&closest!==prev.closest)report.handSwitches.push({frame:i/2,from:prev.closest,to:closest});
  }
  const sample={frame:i/2,actualDeg:ay*DEG,commandDeg:cy*DEG,errorDeg:error,wallFacing:R.dot(R.unit([actual[0],0,actual[2]]),normal),commandWallFacing:R.dot(command,normal),hands:hands.map(h=>({side:h.side,touching:h.touching,gap:h.gap}))};
  first??=sample;last=sample;if(i%10===0||!prev)report.samples.push(sample);prev={f,ay,cy,closest};
 }
 report.first=first;report.last=last;report.geometry=base;
 for(const reach of Object.values(report.footReach)){reach.meanGapM=reach.samples?reach.sumGapM/reach.samples:0;reach.contactFraction=reach.samples?reach.contacts/reach.samples:0;delete reach.sumGapM;}
 if(!report.slideTicks)report.failures.push('Slide not reached');
 if(!report.settledTicks)report.failures.push('Slide blend never completes');
 if(report.maxHeadingErrorDeg>15)report.failures.push('settled heading differs from command by >15deg');
 if(report.maxHeadingStepDeg>8)report.failures.push('heading jumps >8deg at120Hz');
 if(report.maxPalmGapM>.02)report.failures.push('claimed palm contact gap >2cm');
 if(report.maxSoleGapM>.02)report.failures.push('claimed sole contact gap >2cm');
 if(turning&&Math.abs(report.commandSweepDeg)<300)report.failures.push('insufficient yaw sweep for rotation coverage');
 if(turning&&Math.sign(report.actualSweepDeg)!==Math.sign(report.commandSweepDeg))report.failures.push('actual turn follows wrong direction');
 if(base.jointStepsDeg[0]?.value>12)report.failures.push('joint step >12deg at120Hz');
 for(const failure of base.failures)report.failures.push(failure);
 return report;
}
async function main(){
 const args=process.argv.slice(2),only=args.find(x=>x.startsWith('--cases='))?.slice(8).split(','),reports=[];fs.mkdirSync(OUT,{recursive:true});
 for(const[name,file,turning]of cases){if(only&&!only.includes(name))continue;const fixture=read(file);if(turning){fixture.request.endTime=6;fixture.request.source.totalDuration=6;fixture.request.source.directionMeta={...fixture.request.source.directionMeta,totalDuration:6};}
  const result=await V.replay(fixture,{slideLegBlend:1,slidePelvisBlend:1,...(turning?{rootYawStop:40}:{})}),base=V.measure(result,name),report=headingChecks(result,base,name,turning);report.sourceHashes=sourceHashes;report.completedAt=new Date().toISOString();reports.push(report);
  fs.writeFileSync(path.join(OUT,name+'.json'),JSON.stringify(report,null,2));
  if(args.includes('--models'))fs.writeFileSync(path.join(OUT,name+'.model.json.gz'),z.gzipSync(JSON.stringify({names:result.run.names,parents:result.run.parents,settings:result.settings,frames:result.model.frames}),{level:1}));
  console.log(JSON.stringify({name,failures:report.failures,sweep:report.commandSweepDeg,actualSweep:report.actualSweepDeg,maxHeadingError:report.maxHeadingErrorDeg,maxHeadingStep:report.maxHeadingStepDeg,maxHandStep:report.maxHandStepM,joint:base.jointStepsDeg[0],review:base.review}));
 }
 const summary={passed:reports.length>0&&reports.every(r=>!r.failures.length),reports};fs.writeFileSync(path.join(OUT,'report.json'),JSON.stringify(summary,null,2));if(args.includes('--strict')&&!summary.passed)process.exitCode=1;
}
if(require.main===module)main().catch(e=>{console.error(e);process.exitCode=1;});
module.exports={headingChecks,cases};
