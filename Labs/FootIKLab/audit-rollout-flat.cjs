const fs=require('node:fs'),path=require('node:path'),K=require('./footik.js'),F=require('./surface.js'),R=require('./recovery.js'),S=require('./support.js');
const read=p=>JSON.parse(fs.readFileSync(path.join(__dirname,p),'utf8')),rig=read('data/rig.json'),state=read('snapshots/flat-rollout-current-state.json');
const angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(a),R.unit(b)))))*180/Math.PI;
const flex=(p,l)=>angle(R.sub(p.points[l.knee],p.points[l.hip]),R.sub(p.points[l.foot],p.points[l.knee]));
const reports=[];
for(const [label,file] of[['user rollout','model-viewer-walkf-source.json'],['current lab NN','flat-rollout-corrected-source.json']]){
 const run=K.decode(read('snapshots/'+file),rig.parents),m=F.prepare(run,{...state.settings,slopeAngle:0});
 const rows=[];
 for(let n=0;n<=run.duration*60;n++){
  const f=m.sample(n/60),prev=m.sample(Math.max(0,(n-1)/60));
  for(const side of['L','R']){
   const leg=S.leg(f.raw,run.names,side),error=R.sub(R.sub(f.pose.points[leg.knee],f.pose.points[leg.hip]),R.sub(f.raw.points[leg.knee],f.raw.points[leg.hip]));
   rows.push({frame:n,side,kneeErrorCm:R.length(error)*100,flex:flex(f.pose,leg),rawFlex:flex(f.raw,leg),step:Math.abs(flex(f.pose,leg)-flex(prev.pose,leg)),rawStep:Math.abs(flex(f.raw,leg)-flex(prev.raw,leg)),state:f.feet[side==='L'?0:1].state});
  }
 }
 const summary={label,maxKneeErrorCm:Math.max(...rows.map(r=>r.kneeErrorCm)),maxAddedFlexDegrees:Math.max(...rows.map(r=>Math.abs(r.flex-r.rawFlex))),maxKneeStep:Math.max(...rows.map(r=>r.step)),maxRawKneeStep:Math.max(...rows.map(r=>r.rawStep)),worst:rows.toSorted((a,b)=>(b.step-b.rawStep)-(a.step-a.rawStep)).slice(0,8)};
 reports.push({summary,rows});
}
const name=process.argv[2]||'before';fs.writeFileSync(path.join(__dirname,`snapshots/rollout-flat-${name}.json`),JSON.stringify(reports,null,2));console.log(JSON.stringify(reports.map(r=>r.summary),null,2));
