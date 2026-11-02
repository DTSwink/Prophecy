'use strict';
// Optional complete native floor query. Terrain snapshots are immutable;
// changing shoe offsets are copied on every call, including signed zero.
function create(tiles){
 const solve=globalThis.__footikTerrainFloor;
 if(typeof solve!=='function'||!Array.isArray(tiles)||tiles.length>256)return null;
 const prefix=new Float64Array(5+13*tiles.length);prefix[0]=tiles.length;
 let at=5;
 for(const t of tiles){
  const row=[...t.point,...t.u,...t.v,...t.bounds];
  if(row.length!==13||!row.every(Number.isFinite)||t.bounds[0]>=t.bounds[1]||t.bounds[2]>=t.bounds[3])return null;
  prefix.set(row,at);at+=13;
 }
 let input=null,count=-1,cached=null,cachedValue;const output=new Float64Array(1);
 const floor=function floor(ankle,offsets){
  if(!ankle||ankle.length!==3||!Number.isFinite(ankle[0])||!Number.isFinite(ankle[1])||!Number.isFinite(ankle[2])||!Array.isArray(offsets)||offsets.length>64||offsets.length%8)return null;
  if(count!==offsets.length){count=offsets.length;input=new Float64Array(prefix.length+3*count);input.set(prefix);input[1]=count;}
  input[2]=ankle[0];input[3]=ankle[1];input[4]=ankle[2];let k=prefix.length;
  for(const p of offsets){
   if(!p||p.length!==3||!Number.isFinite(p[0])||!Number.isFinite(p[1])||!Number.isFinite(p[2]))return null;
   input[k++]=p[0];input[k++]=p[1];input[k++]=p[2];
  }
  // Reach projection often requests the exact same floor on successive
  // iterations. Compare values, not array identity: callers may mutate a shoe
  // in place. Object.is also keeps +0/-0 distinct. One entry bounds storage
  // to the last whole shoe and avoids an otherwise redundant host transition.
  if(cached&&cached.length===3+3*count&&Object.is(cached[0],input[2])&&Object.is(cached[1],input[3])&&Object.is(cached[2],input[4])){
   let same=true;for(let i=3;i<cached.length;i++)if(!Object.is(cached[i],input[prefix.length+i-3])){same=false;break;}
   if(same)return cachedValue;
  }
  if(!solve(input,output)||!Number.isFinite(output[0]))return null;
  if(!cached||cached.length!==3+3*count)cached=new Float64Array(3+3*count);
  cached[0]=input[2];cached[1]=input[3];cached[2]=input[4];
  for(let i=3;i<cached.length;i++)cached[i]=input[prefix.length+i-3];
  cachedValue=output[0];return cachedValue;
 };
 const solveReach=globalThis.__footikTerrainReach;let reachInput=null,reachCount=-1;const reachOutput=new Float64Array(3);
 if(typeof solveReach==='function')floor.reachable=function(target,hip,reach,offsets){
  if(![target,hip].every(a=>a&&a.length===3&&a.every(Number.isFinite))||!Number.isFinite(reach)||reach<0||!Array.isArray(offsets)||offsets.length>64||offsets.length%8)return null;
  if(reachCount!==offsets.length){reachCount=offsets.length;reachInput=new Float64Array(prefix.length+3*reachCount+4);reachInput.set(prefix);reachInput[1]=reachCount;}
  reachInput.set(target,2);let k=prefix.length;
  for(const p of offsets){if(!p||p.length!==3||!p.every(Number.isFinite))return null;reachInput.set(p,k);k+=3;}
  reachInput.set(hip,k);reachInput[k+3]=reach;
  if(!solveReach(reachInput,reachOutput)||!reachOutput.every(Number.isFinite))return null;
  return Array.from(reachOutput);
 };
 const solveRotation=globalThis.__footikTerrainRotationClearance,rotationInput=new Float64Array(prefix.length+26),rotationOutput=new Float64Array(1);
 rotationInput.set(prefix);rotationInput[1]=16;
 if(typeof solveRotation==='function')floor.rotationClearance=function(ankle,pose,leg,from,to,ceiling,amount,mode){
  const point=pose?.points?.[leg?.foot],local=leg?.toeLocal;
  if(![ankle,point,local].every(a=>a&&a.length===3&&a.every(Number.isFinite))||!['L','R'].includes(leg.side)||![from?.footQ,from?.toeQ,to?.footQ,to?.toeQ].every(q=>q&&q.length===4&&q.every(Number.isFinite))||!Number.isFinite(ceiling)||!Number.isFinite(amount)||amount<0||amount>1||(mode!==0&&mode!==1))return null;
  rotationInput.set(ankle,2);let k=prefix.length;rotationInput.set(point,k);k+=3;rotationInput.set(local,k);k+=3;rotationInput[k++]=leg.side==='L'?1:-1;
  for(const q of [from.footQ,from.toeQ,to.footQ,to.toeQ]){rotationInput.set(q,k);k+=4;}
  rotationInput[k++]=ceiling;rotationInput[k++]=amount;rotationInput[k]=mode;
  return solveRotation(rotationInput,rotationOutput)&&Number.isFinite(rotationOutput[0])?rotationOutput[0]:null;
 };
 return floor;
}
module.exports={create};
