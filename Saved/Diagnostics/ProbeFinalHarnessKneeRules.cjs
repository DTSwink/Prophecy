// Read-only probe of the authoritative harness functions; no UE or harness edits.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const root = 'C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/';
const regular = fs.readFileSync(root+'build_final_harness_standalone.py','utf8');
const live = fs.readFileSync(root+'build_final_harness_live_standalone.py','utf8');
function extract(text,name) {
  const begin=text.indexOf('    function '+name+'(');
  assert(begin>=0,name);
  const end=text.indexOf('\n    function ',begin+1);
  return text.slice(begin,end);
}
const dot3=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
const mul3=(a,s)=>a.map(x=>x*s);
const add3=(a,b)=>a.map((x,i)=>x+b[i]);
const sub3=(a,b)=>a.map((x,i)=>x-b[i]);
const norm3=a=>Math.hypot(...a);
const normalize3=a=>mul3(a,1/Math.max(norm3(a),1e-15));
const cross3=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const rotateAroundAxis=(v,n,a)=>add3(add3(mul3(v,Math.cos(a)),mul3(cross3(n,v),Math.sin(a))),mul3(n,dot3(n,v)*(1-Math.cos(a))));
const worldVectorToLocal=(axes,v)=>axes.map(a=>dot3(a,v));
const localVectorToWorld=(axes,v)=>axes.reduce((s,a,i)=>add3(s,mul3(a,v[i])),[0,0,0]);
const context={dot3,mul3,add3,sub3,norm3,normalize3,cross3,clamp,rotateAroundAxis,worldVectorToLocal,localVectorToWorld,
  fallbackPoleFor:()=>[1,0,0],standaloneStablePerpendicular:()=>[1,0,0],
  standaloneLiveIdleThighPoleReference:()=>({poleThighLocal:[1,0,0],initializationId:0,forwardDot:1})};
vm.createContext(context);
for(const name of ['standaloneFootLocalPoleWorld','standaloneBlendPoleFootLocal']) vm.runInContext(extract(regular,name),context);
vm.runInContext(extract(live,'standaloneLiveLegPoleReference'),context);
const I=[[1,0,0],[0,1,0],[0,0,1]],hip=[0,0,0],ankle=[0,0,-.9];
const angle=(a,b)=>Math.acos(clamp(dot3(normalize3(a),normalize3(b)),-1,1))*180/Math.PI;
const yaw=I.map(a=>rotateAroundAxis(a,[0,0,1],Math.PI/3));
const before=context.standaloneFootLocalPoleWorld(I,[1,0,0],hip,ankle);
const after=context.standaloneFootLocalPoleWorld(yaw,[1,0,0],hip,ankle);
assert(Math.abs(angle(before,after)-60)<1e-9);
const spec={hip:0,knee:1,ankle:2,side:'left'};
const refs=[-.000001,.000001].map(e=>context.standaloneLiveLegPoleReference({points:[hip,[0,e,-.45],ankle],axes:[I,I,I]},spec));
assert(refs.every(r=>r.source==='idle_thigh_rotation_for_near_straight_v1'));
assert(angle(refs[0].poleWorld,refs[1].poleWorld)<1e-9);
const start=[1,0,0],end=normalize3([1,1,0]);
const mixed=context.standaloneBlendPoleFootLocal(start,end,.4);
const p179=context.standaloneFootLocalPoleWorld(I.map(a=>rotateAroundAxis(a,[0,0,1],179*Math.PI/180)),mixed,hip,ankle);
const p181=context.standaloneFootLocalPoleWorld(I.map(a=>rotateAroundAxis(a,[0,0,1],181*Math.PI/180)),mixed,hip,ankle);
assert(Math.abs(angle(p179,p181)-2)<1e-9);
const result={scope:'Synthetic probes of extracted harness functions, not a UE rollout or accepted fix',footRotationDegrees:60,carriedPoleRotationDegrees:angle(before,after),nearStraightPositionPoleFlipDegrees:180,nearStraightHarnessPoleChangeDegrees:angle(refs[0].poleWorld,refs[1].poleWorld),nearStraightThresholdCm:refs[0].reliableBendThresholdM*100,yawWrapPoleChangeDegrees:angle(p179,p181)};
fs.writeFileSync('Saved/Diagnostics/FinalHarnessKneeRules-probe.json',JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));
