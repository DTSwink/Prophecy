const fs=require('fs'),assert=require('assert/strict'),R=require('./recovery.js');
const manifest=JSON.parse(fs.readFileSync(__dirname+'/data/manifest.json'));
const angle=(a,b)=>R.length(R.qlog(R.qm(R.qinv(a),b)));
let cases=0;
for(const clip of manifest.clips)for(const v of clip.variants){
 const b=fs.readFileSync(__dirname+'/'+v.file),m=R.prepare(v,b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),clip,manifest.names,manifest.parents);
 for(const turn of [-179,-90,90,179]){
  const opt={spineTurn:turn,duration:1,inertia:.5},base=R.sample(m,m.attackSeconds),end=R.sample(m,m.attackSeconds,opt);
  for(let i=1;i<=5;i++){const j=m.names.indexOf('spine_0'+i),expected=R.qm(R.qexp([0,turn*Math.PI/180*i/5,0]),base.q[j]);assert(angle(expected,end.q[j])<1e-8,'spine distribution');}
  for(let j=0;j<m.names.length;j++){
   if(!m.upper[j]){assert.deepEqual(end.points[j],base.points[j]);assert.deepEqual(end.q[j],base.q[j]);}
   else {const p=m.parents[j];assert(Math.abs(R.length(R.sub(end.points[j],end.points[p]))-R.length(R.sub(base.points[j],base.points[p])))<1e-8,'length');}
  }
  const seam=R.sample(m,m.attackSeconds+1e-8,opt);
  for(let j=0;j<m.names.length;j++){assert(angle(end.q[j],seam.q[j])<1e-5,'tail rotation seam');assert(R.length(R.sub(end.points[j],seam.points[j]))<1e-5,'tail position seam');}
  const idle=R.sample(m,m.attackSeconds+1,opt);assert.strictEqual(idle,m.idlePose,'idle target changed');
  const dt=1e-7,after=R.sample(m,m.attackSeconds+dt,opt),previous=R.sample(m,m.attackSeconds-1e-6,opt);
  for(let j=0;j<m.names.length;j++)if(m.inertial[j]){const actualWorld=R.mul(R.qlog(R.qm(after.q[j],R.qinv(end.q[j]))),1/dt),expectedWorld=R.mul(R.qlog(R.qm(end.q[j],R.qinv(previous.q[j]))),1e6);assert(R.length(R.sub(actualWorld,expectedWorld))<.002,'turned visible world angular velocity mismatch');}
  for(const t of [.1,.5,.9]){const p=R.sample(m,m.attackSeconds+t,opt);assert(p.points.flat().every(Number.isFinite));assert(p.axes.flat(2).every(Number.isFinite));}
  cases++;
 }
}
console.log(cases+' twisted attacks: distribution, fixed pelvis/legs, lengths, return continuity and original idle passed');
