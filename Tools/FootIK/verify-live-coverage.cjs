'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const K=require('../../Labs/FootIKLab/footik.js'),J=require('./live-join.cjs'),R=require('../../Labs/FootIKLab/recovery.js');
const input=JSON.parse(fs.readFileSync('Saved/Diagnostics/FootIKPort20261030/walk-stairs.input.json','utf8'));
const run=K.decode(input.source,input.parents),pose=K.at(run,.5),names=run.names;
const result={frame:{pose,feet:['L','R'].map(side=>{const l=K.stableLeg(pose,names,side);return {target:pose.points[l.foot],contact:null};})}};
const axes=[[1,0,0],[0,1,0],[0,0,1]],a={current:pose,names,coverage:{center:pose.points[0],extent:[20,20,20],axes}};
assert(J.covered(a,result));
const foot=names.indexOf('foot_l'),l=K.stableLeg(pose,names,'L'),shoe=K.geometry(pose,l).map(o=>R.add(pose.points[foot],o));
const maxX=Math.max(...shoe.map(p=>p[0])),ankle=pose.points[foot][0];assert(maxX>ankle);
// Both ankle centers fit but the left shoe and its influence neighborhood do
// not. A newly captured raised tread just beyond that boundary is relevant.
a.coverage={center:[ankle-10,pose.points[0][1],pose.points[0][2]],extent:[10+(maxX-ankle)/2,20,20],axes};
assert(Math.abs(ankle-a.coverage.center[0])<a.coverage.extent[0]);assert(!J.covered(a,result));
// Even when the complete shoe fits, its32cm terrain-influence margin must fit.
a.coverage.extent[0]=10+maxX-ankle+.2;assert(!J.covered(a,result));
a.coverage={center:pose.points[0],extent:[20,20,20],axes};
const moved=structuredClone(result);moved.frame.feet[0].contact={point:[100,0,0]};assert(!J.covered(a,moved));
const shifted=structuredClone(result);shifted.frame.pose.points=shifted.frame.pose.points.map(p=>R.add(p,[100,0,0]));assert(!J.covered(a,shifted));
for(const yaw of [0,.37,Math.PI/2,-1.1]){
 const q=R.qexp([0,yaw,0]);a.coverage.axes=axes.map(v=>R.rotate(q,v));assert(J.covered(a,result));
}
assert.deepEqual(result.frame.pose,pose);
console.log(JSON.stringify({passed:true,wholeShoe:true,influenceMargin:true,correctedFoot:true,materialPin:true,rotatedCoverage:true,noPoseMutation:true}));
