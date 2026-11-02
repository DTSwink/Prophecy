'use strict';
// Immutable entry-corridor wire layout; matches ProphecyFootIKEntryKernel.h.
function pack({nodes,quality,hip,knee,foot,leg,surfaces}){
 const joint=j=>[...j.c1,...j.c2,j.sinY,j.sinZ,j.twist];
 const values=[quality?1:0,nodes.length,...joint(hip),...knee.axisParent,knee.idleBend,knee.max,...knee.refRelative,...joint(foot)];
 if(nodes.length!==25&&nodes.length!==33)return null;
 for(const c of nodes){const planes=typeof surfaces==='function'?surfaces(c.u,false):surfaces;
  if(c.corners.length>32||planes.length>64)return null;
  values.push(c.u,...c.parentQ,...c.hipPoint,...c.local.p[leg.knee],...c.local.p[leg.foot],...c.residual[0],...c.residual[1],...c.footResidual,...c.wanted,...c.v,c.corners.length,planes.length);
  for(const p of c.corners)values.push(...p);
  for(const p of planes){if(!p.origin||!p.u||!p.normal||!p.v||!p.bounds||p.bounds.length!==4)return null;values.push(...p.origin,...p.u,...p.normal,...p.v,...p.bounds,p.finiteSlab?1:0,p.box?.dims?.[1]??0);}
 }
 return values.every(Number.isFinite)?values:null;
}
function solve(parameters){
 if(typeof globalThis.__footikEntrySolve!=='function')return false;
 const data=pack(parameters);if(!data)return false;
 const input=new Float64Array(data),output=new Float64Array(parameters.nodes.length*7);
 if(!globalThis.__footikEntrySolve(input,output))return false;
 if(!output.every(Number.isFinite))throw Error('Nonfinite native entry corridor');
 for(let i=0;i<parameters.nodes.length;i++)parameters.nodes[i].v=Array.from(output.subarray(i*7,i*7+7));return true;
}
module.exports={pack,solve};
