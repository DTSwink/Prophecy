// Read-only baseline audit: actual NN on flat ground, plus independent accepted
// native NN captures. No Torch, inference worker, server or browser required.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js');
const rig=JSON.parse(fs.readFileSync(new URL('./data/rig.json',import.meta.url)));
const checks=[],cases=[],check=(name,condition)=>{assert(condition,name);checks.push(name);};
const mean=values=>values.reduce((a,b)=>a+b,0)/values.length;
const suffix={backward:'B',left:'LR',right:'RL'};
for(const gait of ['walk','run'])for(const direction of ['backward','left','right']){
 const data=JSON.parse(fs.readFileSync(new URL(`.nn-cache/directional-${gait}-${direction}.json`,import.meta.url)));
 const native=JSON.parse(fs.readFileSync(new URL(`../../Saved/Diagnostics/OmniRecord20261015/M_Neutral_${gait==='walk'?'Walk':'Run'}_Loop_${suffix[direction]}.json`,import.meta.url)));
 const run=K.decode(data,rig.parents),model=K.prepare(run,{...K.defaults,gait,direction,terrain:'flat',phase:.21});
 const desired=direction==='backward'?[0,0,-1]:direction==='left'?[-1,0,0]:[1,0,0];
 const headings={head:[],pelvis:[],leftToe:[],rightToe:[]};let maxFlatDeviation=0,maxFlatRotationError=0;
 for(const frame of model.frames){
  for(let j=0;j<run.names.length;j++){
   maxFlatDeviation=Math.max(maxFlatDeviation,R.length(R.sub(frame.pose.points[j],frame.raw.points[j])));
   maxFlatRotationError=Math.max(maxFlatRotationError,1-Math.abs(R.dot(frame.pose.q[j],frame.raw.q[j])));
  }
  for(const name of ['head','pelvis']){
   const forward=R.rotate(frame.pose.q[run.names.indexOf(name)],[0,-1,0]);forward[1]=0;
   headings[name].push(R.dot(R.unit(forward),desired));
  }
  for(const side of ['l','r']){
   const forward=R.sub(frame.pose.points[run.names.indexOf('ball_'+side)],frame.pose.points[run.names.indexOf('foot_'+side)]);forward[1]=0;
   headings[side==='l'?'leftToe':'rightToe'].push(R.dot(R.unit(forward),desired));
  }
 }
 const actual=Object.fromEntries(Object.entries(headings).map(([key,values])=>[key,mean(values)])),reference={};
 for(const name of ['head','pelvis']){
  const index=native.names.indexOf(name);
  // Native recording +Y matches shared renderer's -Y after the documented
  // handedness conversion. Compare heading in each motion's own world basis.
  reference[name]=mean(native.rows.map(row=>{
   const forward=R.rotate(row.pose[index].slice(3),[0,1,0]);forward[2]=0;
   return R.dot(R.unit(forward),native.facing_world);
  }));
 }
 for(const side of ['l','r']){
  const foot=native.names.indexOf('foot_'+side),toe=native.names.indexOf('ball_'+side);
  reference[side==='l'?'leftToe':'rightToe']=mean(native.rows.map(row=>{
   const forward=R.sub(row.pose[toe].slice(0,3),row.pose[foot].slice(0,3));forward[2]=0;
   return R.dot(R.unit(forward),native.facing_world);
  }));
 }
 const speed=R.length(R.sub(data.roots.at(-1),data.roots[0]))/((data.roots.length-1)/data.fps);
 const nativeSpeed=R.length(native.rows[0].target_cm_s)/100,prefix=gait+'/'+direction+' ';
 check(prefix+'flat output is exact NN position/orientation',maxFlatDeviation<1e-8&&maxFlatRotationError<1e-12);
 check(prefix+'rendered head faces commanded body heading',actual.head>.95);
 check(prefix+'head, pelvis and toes agree with accepted native NN heading statistics',Object.keys(actual).every(key=>Math.abs(actual[key]-reference[key])<.03));
 check(prefix+'actual native directional root speed',Math.abs(speed-nativeSpeed)<.0001);
 cases.push({gait,direction,maxFlatDeviation,maxFlatRotationError,headingCosineMean:actual,nativeHeadingCosineMean:reference,speed,nativeSpeed});
}
fs.writeFileSync(new URL('./directional-flat-baseline-verification.json',import.meta.url),JSON.stringify({count:checks.length,checks,cases},null,2));
console.log(JSON.stringify({passed:checks.length,cases}));
