'use strict';
const R=require('../../Labs/FootIKLab/recovery.js'),S=require('../../Labs/FootIKLab/support.js'),canonicalFootPoints=S.footPoints;
const planeValues=p=>p?.origin&&p.u&&p.normal&&p.v&&p.bounds?.length===4?[...p.origin,...p.u,...p.normal,...p.v,...p.bounds,p.finiteSlab?1:0,p.box?.dims?.[1]??0]:null;
function pack({goal,l,parents,joints,rotation,point,wantedAxis,wantedPole,e,side,targetShift,previousPole,dt,plane,terrain}){
 if(S.footPoints!==canonicalFootPoints)return null;
 const hip=joints.joints[l.hip],knee=joints.joints[l.knee],foot=joints.joints[l.foot],toe=joints.joints[l.toe],swing=j=>[...j.c1,...j.c2,j.sinY,j.sinZ,j.twist],previousDrop=e.contactDrop?.[side],lastTravel=e.contactTravel?.[side];
 const data=[...goal.q[l.pelvis],...goal.q[parents[l.hip]],...goal.points[l.hip],...goal.points[l.knee],...goal.points[l.foot],...goal.points[l.toe],...goal.q[l.hip],...goal.q[l.knee],...goal.q[l.foot],...goal.q[l.toe],
 l.upper,l.lower,l.reach,...l.normal,...l.upperAxis,...l.lowerAxis,...l.hipQ,...l.kneeQ,...l.kneeLocal,...l.ankleLocal,...l.toeLocal,
 ...swing(hip),...knee.axisParent,...knee.axisChild,knee.idleBend,knee.min,knee.max,...knee.refRelative,...swing(foot),...foot.refRelative,...swing(toe),...toe.refRelative,
 ...point,...rotation.footQ,...rotation.toeQ,...wantedAxis,...wantedPole,...e.w,...e.n,...targetShift,
 previousPole?1:0,...(previousPole?.axis||[0,0,0]),...(previousPole?.pole||[0,0,0]),Number.isFinite(previousDrop)?1:0,Number.isFinite(previousDrop)?previousDrop:0,Number.isFinite(lastTravel)?1:0,Number.isFinite(lastTravel)?lastTravel:0,dt,side==='L'?1:-1];
 if(data.length!==158)throw Error('Leg kernel fixed contract changed');
 const active=planeValues(plane),surfaces=terrain.surfaces;if(!active||surfaces.length>64)return null;data.push(...active,surfaces.length);
 for(const surface of surfaces){const p=planeValues(surface);if(!p)return null;data.push(...p);}return data.every(Number.isFinite)?data:null;
}
function flatten(goal,l,e,side){return [...goal.q[l.hip],...goal.points[l.knee],...goal.q[l.knee],...goal.points[l.foot],...goal.q[l.foot],...goal.points[l.toe],...goal.q[l.toe],e.contactDrop[side],e.contactTravel[side],...e.poles[side].axis,...e.poles[side].pole];}
function solve(parameters){
 if(typeof globalThis.__footikLegContact!=='function')return null;
 const data=pack(parameters);if(!data)return null;
 const input=new Float64Array(data),output=new Float64Array(33);if(!globalThis.__footikLegContact(input,output))return null;
 if(!output.every(Number.isFinite))throw Error('Nonfinite native leg contact');
 const {goal,l,e,side}=parameters,p={...goal,points:goal.points.slice(),q:goal.q.slice(),axes:goal.axes.slice()},array=(at,n)=>Array.from(output.subarray(at,at+n));
 p.q[l.hip]=array(0,4);p.points[l.knee]=array(4,3);p.q[l.knee]=array(7,4);p.points[l.foot]=array(11,3);p.q[l.foot]=array(14,4);p.points[l.toe]=array(18,3);p.q[l.toe]=array(21,4);
 for(const j of[l.hip,l.knee,l.foot,l.toe])p.axes[j]=R.toAxes(p.q[j]);
 (e.contactDrop||={})[side]=output[25];(e.contactTravel||={})[side]=output[26];e.poles[side]={axis:array(27,3),pole:array(30,3)};return p;
}
module.exports={pack,flatten,solve};
