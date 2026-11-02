'use strict';
// Wire layout shared with ProphecyFootIKArmKernel.h. No math is performed here:
// preserve every input double, including signed zero, in its original order.
function pack({pose,a,parents,joints,nearest,requestedPoint,n,wallUp,shoulderOut,reach,handQ}){
 const upper=joints.joints[a.a],lower=joints.joints[a.b],wrist=joints.joints[a.c],rig=joints.arms[a.side];
 const values=[...pose.points[a.a],...pose.points[a.b],...pose.points[a.c],...pose.q[parents[a.a]],...pose.q[a.a],...pose.q[a.b],...pose.q[a.c],
  ...upper.c1,...upper.c2,upper.sinY,upper.sinZ,upper.twist,
  ...lower.axisParent,lower.idleBend,lower.min,lower.max,...lower.refRelative,
  ...wrist.c1,...wrist.c2,wrist.sinY,wrist.sinZ,wrist.twist,...wrist.refRelative,
  ...rig.basisToBody,...rig.forearmDirection,
  ...nearest,...requestedPoint,...n,...wallUp,...shoulderOut,a.sign,reach,...handQ,a.bracePole?1:0,...(a.braceAxis||[0,0,0]),...(a.bracePole||[0,0,0])];
 if(values.length!==96||!values.every(Number.isFinite))throw Error('Invalid complete brace-fit kernel input');return values;
}
function flatten(best,a){return [...best.local.q[a.a],...best.local.q[a.b],...best.local.q[a.c],...best.valid.q[a.a],...best.valid.q[a.b],...best.valid.q[a.c],...best.valid.points[a.b],...best.valid.points[a.c],...best.point,best.gap];}
function unpack(values,a){
 if(values.length!==34||!values.every(Number.isFinite))throw Error('Invalid complete brace-fit kernel output');
 const local=[],q=[],points=[];for(let i=0;i<3;i++){const j=[a.a,a.b,a.c][i];local[j]=values.slice(i*4,i*4+4);q[j]=values.slice(12+i*4,16+i*4);}
 points[a.b]=values.slice(24,27);points[a.c]=values.slice(27,30);return {local:{q:local},valid:{q,points},point:values.slice(30,33),gap:values[33]};
}
module.exports={pack,flatten,unpack};
