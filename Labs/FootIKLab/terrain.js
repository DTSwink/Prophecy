(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
// footPoints emits ordered eight-corner boxes (forward, side, up sign bits).
const faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]];
function clip(poly,axis,bound,sign){
 const out=[];let a=poly[poly.length-1],da=sign*(a[axis]-bound);
 for(const b of poly){const db=sign*(b[axis]-bound);
  if((da>=0)!==(db>=0)){const t=da/(da-db);out.push(a.map((v,j)=>v+(b[j]-v)*t));}
  if(db>=0)out.push(b);a=b;da=db;
 }return out;
}
function create(s){
 const start=1.8,h=s.height/100,d=s.depth/100,n=s.steps,end=start+d*n,down=s.terrain==='down',stairs=['stairs','down'].includes(s.terrain),tiles=[];
 const level=i=>down?(n-i)*h:i*h;
 if(stairs){
  tiles.push({id:'entry',x0:-2,x1:2,z0:-4,z1:start,y:level(0)});
  for(let i=0;i<n;i++)tiles.push({id:'step'+i,x0:-2,x1:2,z0:start+i*d,z1:start+(i+1)*d,y:level(i+1)});
  tiles.push({id:'exit',x0:-2,x1:2,z0:end,z1:35,y:level(n)});
 }else if(s.terrain==='uneven'){
  tiles.push({id:'entry',x0:-2,x1:2,z0:-4,z1:start,y:0});
  for(let i=0;i<n;i++)for(let side=0;side<2;side++)tiles.push({id:'tile'+i+'_'+side,x0:side===0?-2:0,x1:side===0?0:2,z0:start+i*d,z1:start+(i+1)*d,y:h*(.25+.75*(.5+.5*Math.sin(i*1.83+side*2.7)))});
  tiles.push({id:'exit',x0:-2,x1:2,z0:end,z1:35,y:0});
 }else tiles.push({id:'flat',x0:-2,x1:2,z0:-4,z1:35,y:0});
 const hit=(x,z)=>tiles.find(t=>x>=t.x0-1e-9&&x<=t.x1+1e-9&&z>=t.z0-1e-9&&z<t.z1-1e-9)||null;
 const height=(x,z)=>hit(x,z)?.y??0;
 const rootHeight=z=>stairs?level(0)+(down?-1:1)*h*clamp((z-start)/d,0,n):0;
 // Minimum shoe height over each tread footprint. Corners alone miss a shoe
 // edge crossing a riser, or a tread corner entering the middle of a box face.
 // Most boxes lie inside one tread: only boundary overlaps need face clipping.
 function floorFor(ankle,offsets){
  let y=-Infinity;
  for(let b=0;b<offsets.length;b+=8){
   const box=offsets.slice(b,b+8);let x0=Infinity,x1=-Infinity,z0=Infinity,z1=-Infinity,minY=Infinity;
   for(const o of box){x0=Math.min(x0,o[0]);x1=Math.max(x1,o[0]);z0=Math.min(z0,o[2]);z1=Math.max(z1,o[2]);minY=Math.min(minY,o[1]);}
   for(const tile of tiles){
    const loX=tile.x0-ankle[0],hiX=tile.x1-ankle[0],loZ=tile.z0-ankle[2],hiZ=tile.z1-ankle[2];
    if(x1<=loX+1e-9||x0>=hiX-1e-9||z1<=loZ+1e-9||z0>=hiZ-1e-9)continue;
    const cuts=[];
    if(x0<loX)cuts.push([0,loX,1]);if(x1>hiX)cuts.push([0,hiX,-1]);
    if(z0<loZ)cuts.push([2,loZ,1]);if(z1>hiZ)cuts.push([2,hiZ,-1]);
    let lowest=minY;
    if(cuts.length){
     lowest=Infinity;
     for(const face of faces){let poly=face.map(i=>box[i]);
      for(const [axis,bound,sign] of cuts){poly=clip(poly,axis,bound,sign);if(!poly.length)break;}
      for(const p of poly)lowest=Math.min(lowest,p[1]);
     }
    }
    y=Math.max(y,tile.y-lowest);
   }
  }
  return Number.isFinite(y)?y:ankle[1];
 }
 function landing(ankle,offsets){
  // The ankle can still be behind a riser while the shoe is landing on its
  // tread. Use the sole's centre, not the ankle ray, to select support.
  const centre=offsets.slice(0,8).reduce((p,o)=>p.map((v,j)=>v+o[j]/8),ankle.slice());
  const tile=hit(centre[0],centre[2]);if(!tile)return null;
  const minZ=Math.min(...offsets.map(o=>o[2])),maxZ=Math.max(...offsets.map(o=>o[2])),minX=Math.min(...offsets.map(o=>o[0])),maxX=Math.max(...offsets.map(o=>o[0]));
  const lo=tile.z0-minZ+.008,hi=tile.z1-maxZ-.008;
  const target=[clamp(ankle[0],tile.x0-minX+.004,tile.x1-maxX-.004),0,lo<=hi?clamp(ankle[2],lo,hi):(lo+hi)/2];
  target[1]=floorFor(target,offsets);
  return {target,tile,local:R.sub(target,[0,tile.y,tile.z0]),height:tile.y};
 }
 return {tiles,start,end,rootHeight,hit,height,floorFor,landing};
}
const api={create};if(typeof module!=='undefined')module.exports=api;else root.FootTerrain=api;
})(globalThis);
