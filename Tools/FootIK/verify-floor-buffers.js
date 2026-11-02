(function(){
 'use strict';
 let checked=0;
 for(const [values,expected] of globalThis.floorFixtures){
  const inputStore=new Float64Array(values.length+4),input=inputStore.subarray(2,values.length+2);input.set(values);
  const store=new Float64Array(5).fill(1234),output=store.subarray(2,3);
  if(__footikTerrainFloor(input,output)!==1)throw Error('Valid floor input rejected at '+checked);
  if(!Object.is(output[0],expected[0]))throw Error('Floor differs at '+checked+': '+output[0]+' / '+expected[0]);
  if(store[0]!==1234||store[1]!==1234||store[3]!==1234||store[4]!==1234)throw Error('Floor wrote beyond its output view');
  checked++;
 }
 const base=globalThis.floorFixtures[0][0],sentinel=new Float64Array([987]);
 const invalid=[new Float64Array(0),new Float64Array([0,0,0,NaN,0]),new Float64Array([0,0,0,Infinity,0]),new Float64Array([257,0,0,0,0]),new Float64Array([0,7,0,0,0]),new Float32Array(base)];
 const inverted=base.slice();if(inverted[0]>0){inverted[14]=10;inverted[15]=-10;invalid.push(new Float64Array(inverted));}
 let rejected=0;
 for(let repeat=0;repeat<2000;repeat++)for(const input of invalid){if(__footikTerrainFloor(input,sentinel)!==0)throw Error('Invalid floor input accepted');if(sentinel[0]!==987)throw Error('Rejected input partially published');rejected++;}
 if(__footikTerrainFloor(new Float64Array(base),new Float64Array(2))!==0)throw Error('Wrong output length accepted');
 const alias=new Float64Array([0,0,1,-0,2]);if(__footikTerrainFloor(alias,alias.subarray(3,4))!==1||!Object.is(alias[3],-0))throw Error('Valid overlapping buffers changed the result');
 print(JSON.stringify({passed:true,exactQueries:checked,offsetViews:true,signedZero:true,rejectedWithoutPublication:rejected+1}));
})();
