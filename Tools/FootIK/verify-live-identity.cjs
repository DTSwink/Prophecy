'use strict';
// A verified raw fallback is not a computed terrain correction. No inference,
// worker, future-horizon change, or suppression of the ongoing planner here.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js'),R=require('../../Labs/FootIKLab/recovery.js'),J=require('./live-join.cjs'),LT=require('./live-terrain.cjs');
const dir=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),packaged=process.argv.includes('--packaged');
const context={structuredClone,performance,FootIKRequire:id=>require(path.resolve(__dirname,id.endsWith('.cjs')?id:'../../Labs/FootIKLab/'+id))};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.resolve(__dirname,packaged?'../../Content/FootIKLab/Runtime.js':'runtime-adapter.js'),'utf8'),context);
const command=a=>JSON.parse(context.FootIKNative.command(JSON.stringify({...a,op:'liveIdentity'})));
const axes=[[1,0,0],[0,1,0],[0,0,1]],previousFeet=[{state:'NN',contact:null},{state:'NN',contact:null}];
let checks=0,zeroFrames=0,affectedFrames=0,materialRejected=0;
const recoveryCounterexamples=[];
function check(a,expected,label){const saved=structuredClone(a),actual=J.identity(a);assert.equal(actual.identity,expected,label);assert.deepEqual(command(a),actual,label+' protocol');assert.deepEqual(a,saved,label+' immutable input');checks++;}
const coverage=p=>({center:p.points[0],extent:[30,30,30],axes});
let sample,names,parents;
for(const name of ['walk-stairs','run-stairs']){
 const input=JSON.parse(fs.readFileSync(path.join(dir,name+'.input.json'))),source=structuredClone(input.source);
 source.poses=source.poses.slice(0,49);source.roots=source.roots.slice(0,49);if(source.rootYawDegrees)source.rootYawDegrees=source.rootYawDegrees.slice(0,49);source.duration=source.totalDuration=1.6;source.directionMeta={...source.directionMeta,totalDuration:1.6};
 const run=K.decode(source,input.parents),base=T.create(input.settings),snapshot={tiles:base.tiles.map(t=>({id:t.id,point:[0,t.y,0],u:[1,0,0],v:[0,0,1],bounds:[t.x0,t.x1,t.z0,t.z1],shaped:t.id.startsWith('step')}))},terrain=LT.create(snapshot),origin=run.poses[0].points[0];
 const rootAtTime=t=>{const p=K.at(run,t).points[0];return [p[0]-origin[0],base.rootHeight(p[2]-origin[2]),p[2]-origin[2]];};
 const model=K.prepare(run,input.settings,{terrain,origin,rootAtTime,influence:(p,legs,t)=>terrain.influence(p,legs,rootAtTime(t)[1],K.geometry),capture:true});
 for(let i=0;i<model.frames.length;i++){
  const frame=model.frames[i],current=frame.raw,prior=i?model.frames[i-1].feet:previousFeet,legs=['L','R'].map(s=>K.stableLeg(current,run.names,s));
  const influence=terrain.influence(current,legs,current.points[0][1],K.geometry),expected=prior.every(f=>f.state==='NN'&&!f.contact)&&influence===0;
  const a={current,parents:input.parents,names:run.names,previousFeet:prior,coverage:coverage(current),terrain:snapshot};
  check(a,expected,name+' '+i);
  if(expected&&frame.influence===0){assert.deepEqual(frame.pose,current,'Canonical zero-weight pose is exactly raw');zeroFrames++;}
  else if(expected)recoveryCounterexamples.push({name,tick:i,canonicalWeight:frame.influence,previousStates:prior.map(f=>f.state)});
  if(influence>0){assert.equal(J.identity(a).identity,false);affectedFrames++;}
  if(prior.some(f=>f.contact)){assert.equal(J.identity(a).identity,false);materialRejected++;}
  if(!sample&&expected){sample=structuredClone(a);names=run.names;parents=input.parents;}
 }
}
assert(sample&&zeroFrames>0&&affectedFrames>0&&materialRejected>0,'Fixture must cover canonical identity, terrain influence, and material pins');
sample.terrain={tiles:[{id:'flat',point:[0,sample.current.points[0][1],0],u:axes[0],v:axes[2],bounds:[-30,30,-30,30],shaped:true}]};sample.previousFeet=previousFeet;
check(sample,true,'Finite matching ground');
check({...sample,terrain:{tiles:[]}},true,'Fresh query with no influencing colliders');
check({...sample,names:undefined,sourceNames:names.slice(1)},true,'Source-name form');
for(const state of ['SWING','ROLL','REACH','SLIDE'])check({...sample,previousFeet:[{state,contact:null},previousFeet[1]]},false,'Active '+state+' receipt');
for(const side of [0,1]){const feet=structuredClone(previousFeet);feet[side].contact={point:[0,0,0],surface:'old'};check({...sample,previousFeet:feet},false,'Material contact '+side);}
check({...sample,previousFeet:undefined},false,'Missing history');check({...sample,coverage:undefined},false,'Missing fresh query coverage');
const shoe=['L','R'].flatMap(s=>{const l=K.stableLeg(sample.current,names,s);return K.geometry(sample.current,l).map(o=>R.add(sample.current.points[l.foot],o));}),maxX=Math.max(...shoe.map(p=>p[0])),height=sample.current.points[0][1];
for(const [gap,accepted] of [[.319,false],[.321,true]]){
 const tile={id:'curb',point:[maxX+gap,height+.1,0],u:axes[0],v:axes[2],bounds:[0,.1,-30,30],shaped:true};
 check({...sample,terrain:{tiles:[...sample.terrain.tiles,tile]}},accepted,'Whole-shoe curb influence '+gap);
}
check({...sample,coverage:{center:[maxX-10,height,0],extent:[10.2,30,30],axes}},false,'Shoe fits but influence margin leaves query');
for(const yaw of [.37,Math.PI/2,-1.1]){const q=R.qexp([0,yaw,0]);check({...sample,coverage:{...sample.coverage,axes:axes.map(v=>R.rotate(q,v))}},true,'Rotated finite query '+yaw);}
const malformed=structuredClone(sample);malformed.current.points[1][0]=NaN;assert.throws(()=>J.identity(malformed),/finite actual pose/);
assert.throws(()=>J.identity({...sample,terrain:{tiles:[{id:'bad'}]}}));
const report={passed:true,packaged,checks,canonicalZeroWeightFrames:zeroFrames,nonzeroInfluenceFramesRejected:affectedFrames,priorMaterialFramesRejected:materialRejected,rawFallbackOutputUnchanged:true,nonNNRecoveryStatesRejected:true,recoveryCounterexamples,note:'NN foot states alone do not certify that a previous corrected recovery has ended. The caller must not preempt actual corrected recovery/terrain return; this operation only validates an already-raw fallback.',wholeShoeAndInfluenceCoverage:true,validCandidateJoinsUnmodified:true};
fs.writeFileSync(path.join(dir,packaged?'live-identity-packaged.json':'live-identity.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
