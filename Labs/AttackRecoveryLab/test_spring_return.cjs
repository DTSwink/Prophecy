const fs=require('fs'),assert=require('assert/strict'),R=require('./recovery.js');
const manifest=JSON.parse(fs.readFileSync(__dirname+'/data/manifest.json')),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
let cases=0,maxEndpointAngle=0,maxEndpointPoint=0,maxBuildMs=0,worst=null;
for(const clip of manifest.clips)for(const v of clip.variants){
 const bytes=fs.readFileSync(__dirname+'/'+v.file),m=R.prepare(v,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length),clip,manifest.names,manifest.parents);
 for(const profile of [{duration:.31,returnEasing:0,inertiaDecay:.5,worldInertia:true},{duration:.6,returnEasing:1,inertiaDecay:1,worldInertia:false},{duration:.1,returnEasing:1,inertiaDecay:4,worldInertia:true},{duration:.31,returnEasing:0,inertiaDecay:0,worldInertia:true}]){
  const o={...profile,inertia:1,springReturn:true,spineTurn:125},tail=m.attackSeconds,end=R.sample(m,tail,o),started=performance.now();
  R.sample(m,tail+.01,o);maxBuildMs=Math.max(maxBuildMs,performance.now()-started);
  const cache=m.turnCache.model.springCache,expected=m.idlePose,raw=R.fk(cache.endpointBeforeSnap,m.parents);
  for(let j=0;j<m.names.length;j++){const error=angle(raw.q[j],expected.q[j])*180/Math.PI;if(error>maxEndpointAngle){maxEndpointAngle=error;worst={attack:clip.name,variant:v.id,bone:m.names[j],profile};}maxEndpointPoint=Math.max(maxEndpointPoint,R.length(R.sub(raw.points[j],expected.points[j])));}
  for(const f of [.000001,.1,.3,.5,.8,.99,.999999]){
   const pose=R.sample(m,tail+f*o.duration,o),local=R.localize(pose.points,pose.q,m.parents);
   assert(pose.points.flat().every(Number.isFinite));assert(pose.axes.flat(2).every(Number.isFinite));
   for(let j=0;j<m.names.length;j++){
    if(!m.upper[j]){assert(R.length(R.sub(pose.points[j],end.points[j]))<1e-8);assert(angle(pose.q[j],end.q[j])<1e-8);}
    else assert(Math.abs(R.length(local.p[j])-R.length(m.locals.at(-1).p[j]))<1e-8,'bone length');
   }
  }
  assert.strictEqual(R.sample(m,tail+o.duration,o),expected,'idle deadline');
  assert.deepEqual(R.sample(m,tail+.07,{...o,inertia:0}),R.sample(m,tail+.07,{...o,inertia:0,springReturn:false}),'zero mode changed');
  // Hold is explicitly irrelevant: no hidden segmentation in this mode.
  assert.deepEqual(R.sample(m,tail+.07,{...o,inertiaHold:0}),R.sample(m,tail+.07,{...o,inertiaHold:.8}),'spring has a hold phase');
  const a=R.sample(m,tail+.07,o);R.sample(m,tail+.19,o);assert.deepEqual(R.sample(m,tail+.07,o),a,'history-dependent sampling');
  cases++;
 }
}
console.log(JSON.stringify({maxEndpointAngle,maxEndpointPoint,worst,maxBuildMs}));
assert(maxEndpointAngle<.1,'visible endpoint angular snap');assert(maxEndpointPoint<.001,'visible endpoint position snap');
console.log(JSON.stringify({cases,maxEndpointAngle,maxEndpointPoint,maxBuildMs,passed:'finite springs, frozen lower, lengths, endpoint residue, zero-mode parity, no hold, deterministic seeking'}));
