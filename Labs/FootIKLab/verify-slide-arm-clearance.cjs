'use strict';
// Recorded policy replay: check actual capsule and box geometry, not palm centres.
const fs=require('fs'),z=require('zlib'),path=require('path'),assert=require('assert/strict');
const V=require('./verify-slide-directions.cjs'),R=require('./recovery.js'),S=require('./surface.js');
const read=p=>JSON.parse(z.gunzipSync(fs.readFileSync(p)));
function measure(m){
 const terrain=S.createTerrain(m.settings),report={minGap:Infinity,worst:null,slideTicks:0,maxArmStepDeg:0};
 for(let i=0;i<m.frames.length;i++){
  const f=m.frames[i];if(!f.slide)continue;report.slideTicks++;
  const plane=terrain.allSurfaces.find(p=>p.id===f.slide.surface);if(!plane)continue;const n=plane.normal,p=f.pose;
  const distance=v=>R.dot(R.sub(v,plane.project(v)),n);
  for(const side of ['l','r']){
   const ids=['upperarm_','lowerarm_','hand_'].map(s=>m.names.indexOf(s+side)),sign=side==='l'?1:-1;
   const q=p.q[ids[2]],x=R.rotate(q,[sign,0,0]),y=R.rotate(q,[0,1,0]),zz=R.rotate(q,[0,0,1]),center=R.add(R.add(p.points[ids[2]],R.mul(x,.0725)),R.mul(y,-.0025));
   const gaps=[distance(p.points[ids[0]])-.0588,distance(p.points[ids[1]])-.0588,distance(p.points[ids[2]])-.0488,distance(center)-Math.abs(R.dot(n,x))*.0725-Math.abs(R.dot(n,y))*.0225-Math.abs(R.dot(n,zz))*.045];
   for(let k=0;k<gaps.length;k++)if(gaps[k]<report.minGap){report.minGap=gaps[k];report.worst={frame:i/2,side,part:k};}
   if(i&&m.frames[i-1].slide)for(const j of ids)report.maxArmStepDeg=Math.max(report.maxArmStepDeg,R.length(R.qlog(R.qm(p.q[j],R.qinv(m.frames[i-1].pose.q[j]))))*180/Math.PI);
  }
 }
 return report;
}
module.exports={measure};
if(require.main===module)(async()=>{
 const files=process.argv.slice(2);assert(files.length,'Supply recorded fixture paths');
 for(const file of files){const start=performance.now(),r=await V.replay(read(file)),base=V.measure(r,path.basename(file)),m={names:r.run.names,parents:r.run.parents,settings:r.settings,frames:r.model.frames},report=measure(m);console.log(JSON.stringify({file,ms:performance.now()-start,...report,failures:base.failures}));assert(report.slideTicks>0);assert(report.minGap>=-.001,'Arm collider penetrates active wall');assert.deepEqual(base.failures,[]);}
})().catch(e=>{console.error(e);process.exitCode=1;});
