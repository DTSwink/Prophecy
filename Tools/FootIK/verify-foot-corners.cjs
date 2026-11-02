'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const {performance}=require('node:perf_hooks');
const {corners}=require('./foot-corners.cjs');
const file=path.resolve(__dirname,'../../Labs/BodyflipLab/support.js'),source=fs.readFileSync(file,'utf8');
const original='const corners=(c,f,s,u,d)=>[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>add(add(add(c,mul(f,x*d[0]/2)),mul(s,y*d[1]/2)),mul(u,z*d[2]/2)))));';
assert.equal(source.split(original).length,2);
const candidate=new Module(file,module);candidate.filename=file;candidate.paths=module.paths;
candidate._compile(source.replace(original,'const corners='+corners.toString()+';'),file);
const before=require(file),after=candidate.exports,R=require('../../Labs/FootIKLab/recovery.js');
let seed=1729;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/0xffffffff*2-1;};
const cases=[];
for(let i=0;i<4096;i++){
 const q=R.unit([random(),random(),random(),random()]),t=R.unit([random(),random(),random(),random()]);
 cases.push({points:[[random()*100,random()*100,random()*100],[random()*100,random()*100,random()*100]],axes:[R.toAxes(q),R.toAxes(t)]});
}
for(const p of cases)for(const side of ['L','R'])assert.deepEqual(after.footPoints(p,0,1,side),before.footPoints(p,0,1,side));
const scalar=(c,f,s,u,d)=>[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>c.map((v,i)=>((v+f[i]*(x*d[0]/2))+s[i]*(y*d[1]/2))+u[i]*(z*d[2]/2)))));
for(const zero of [0,-0])for(const v of [0,-0,1,-1,1e-300,1e300]){
 const args=[[zero,v,-v],[v,zero,zero],[zero,v,zero],[zero,zero,v],[.175,.12,.051]];
 assert.deepEqual(corners(...args),scalar(...args));
}
const measure=api=>{const begin=performance.now();let sum=0;for(let repeat=0;repeat<3;repeat++)for(const p of cases)sum+=api.footPoints(p,0,1,'L')[0][0];return {ms:performance.now()-begin,sum};};
measure(before);measure(after);const ab=[measure(before),measure(after),measure(after),measure(before)];
assert.equal(ab[0].sum,ab[1].sum);
const receipt={passed:true,completeShoes:8192,signedZeroAndExtremeCases:12,beforeMs:(ab[0].ms+ab[3].ms)/2,afterMs:(ab[1].ms+ab[2].ms)/2};
fs.writeFileSync(path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030/foot-corners.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
