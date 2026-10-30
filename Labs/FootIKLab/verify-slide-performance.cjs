'use strict';
// Same recorded NN input on both revisions; no live service or scene changes.
const fs=require('fs'),path=require('path'),z=require('zlib'),Module=require('module'),assert=require('assert/strict');
const folder=path.resolve(__dirname,'../../Saved/FootIKPerf20261029');
const record=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(folder,'current-session.gz'))));
function version(before){
 const cache=new Map();
 function load(file){
  if(!path.extname(file))file+='.js';if(cache.has(file))return cache.get(file).exports;
  if(file.endsWith('.json'))return JSON.parse(fs.readFileSync(file));
  const original=path.join(folder,path.basename(file)),source=before&&fs.existsSync(original)?original:file;
  const m=new Module(file,module);m.filename=file;m.paths=module.paths;cache.set(file,m);
  m.require=id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id);
  m._compile(fs.readFileSync(source,'utf8'),file);return m.exports;
 }
 return {K:load(path.join(__dirname,'footik.js')),C:load(path.join(__dirname,'surface-coupling.js'))};
}
(async()=>{
 const old=version(true),current=version(false),R=require('./recovery.js'),times={before:[],after:[]};
 let expected,actual;
 for(let i=0;i<3;i++)for(const [name,v] of [['before',old],['after',current]]){
  const run=v.K.decode(record.request.source,require('./data/rig.json').parents);run.totalDuration=record.request.totalDuration;
  const start=performance.now(),session=v.C.createSession(run,record.request.settings,async(_,i)=>record.steps[i]);
  const {model}=await session.extend(record.generatedThrough);times[name].push(performance.now()-start);
  if(name==='before')expected=model.frames;else actual=model.frames;
  session.close();
 }
 let position=0,angle=0;
 assert.equal(actual.length,expected.length);
 for(let i=0;i<actual.length;i++){
  assert.deepEqual(actual[i].root,expected[i].root,'Root path is unchanged');
  for(let j=0;j<actual[i].pose.points.length;j++){
   position=Math.max(position,R.length(R.sub(actual[i].pose.points[j],expected[i].pose.points[j])));
   angle=Math.max(angle,R.length(R.qlog(R.qm(actual[i].pose.q[j],R.qinv(expected[i].pose.q[j]))))*180/Math.PI);
  }
 }
 assert(position<.00002&&angle<.003,'Equivalent poses within numerical search tolerance');
 const median=a=>a.slice().sort((a,b)=>a-b)[1];
 const report={passed:true,frames:actual.length,times,medianBeforeMs:median(times.before),medianAfterMs:median(times.after),ratio:median(times.before)/median(times.after),maxPositionMeters:position,maxRotationDegrees:angle,rootExact:true};
 fs.writeFileSync(path.join(folder,'performance-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
