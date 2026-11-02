'use strict';
// Independent, frozen JavaScript oracle. Fixtures remain under Saved; do not
// update the snapshot to hide a native difference after an implementation edit.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),crypto=require('node:crypto');
const K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js'),R=require('../../Labs/FootIKLab/recovery.js');
const dir=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030/floor-native');fs.mkdirSync(dir,{recursive:true});
const oracle=path.join(dir,'oracle-live-terrain.cjs'),filename=path.join(__dirname,'live-terrain.cjs');
if(!fs.existsSync(oracle))throw Error('Freeze the independent pre-kernel live-terrain source first');
const code=fs.readFileSync(oracle,'utf8'),m=new Module(filename,module);m.filename=filename;m.paths=Module._nodeModulePaths(__dirname);m._compile(code,filename);const L=m.exports;
const records=[],labels={};
function sample(label,terrain,ankle,offsets){
 const input=[terrain.tiles.length,offsets.length,...ankle];
 for(const t of terrain.tiles)input.push(...t.point,...t.u,...t.v,...t.bounds);
 for(const o of offsets)input.push(...o);
 const expected=[terrain.floorFor(ankle,offsets)];
 if(!input.every(Number.isFinite)||!expected.every(Number.isFinite))throw Error('Invalid finite fixture');
 records.push({input,expected});labels[label]=(labels[label]||0)+1;
}
const source=JSON.parse(fs.readFileSync(path.join(dir,'../walk-stairs.input.json'))),run=K.decode(source.source,source.parents),standard=T.create(source.settings);
for(const angle of [0,37,90,-135,180]){
 const q=R.qexp([0,angle*Math.PI/180,0]),turn=p=>R.rotate(q,p),terrain=L.create({tiles:standard.tiles.map(t=>({id:t.id,point:turn([0,t.y,0]),u:turn([1,0,0]),v:turn([0,0,1]),bounds:[t.x0,t.x1,t.z0,t.z1]}))});
 for(let i=0;i<=180;i+=12){const pose=K.at(run,i/120);for(const side of ['L','R']){const l=K.stableLeg(pose,run.names,side),offsets=K.geometry(pose,l).map(turn),root=pose.points[0],ankle=turn(R.add(pose.points[l.foot],[0,standard.rootHeight(root[2]),0]));
  for(const shift of [-2.000000001,-2,0,2,2.000000001])sample('gait-rotated-edge',terrain,R.add(ankle,turn([shift,0,0])),offsets);
 }}
}
let seed=0xc0ffee;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;},range=(a,b)=>a+(b-a)*random();
// Include independent bases, overlapping heights and box corners crossing all
// four cuts. Keep the canonical cuboid corner ordering used by the solver.
const prototype=K.at(run,0),leg=K.stableLeg(prototype,run.names,'L'),shoe=K.geometry(prototype,leg);
for(let i=0;i<3000;i++){
 const tiles=[];for(let j=0,n=1+i%7;j<n;j++){const a=range(-Math.PI,Math.PI),c=Math.cos(a),s=Math.sin(a);tiles.push({id:String(j),point:[range(-.6,.6),range(-.4,.4),range(-.6,.6)],u:[c,0,-s],v:[s,0,c],bounds:[-.15,range(.05,.8),-.15,range(.05,.8)]});}
 const terrain=L.create({tiles}),q=R.qexp([range(-1,1),range(-2,2),range(-1,1)]),offsets=shoe.map(p=>R.rotate(q,p)),ankle=[range(-.8,.8),range(-.8,.8),range(-.8,.8)];
 sample('random-face-clipping',terrain,ankle,offsets);
 if(i<30){offsets[0][0]+=.123;sample('mutated-shoe',terrain,ankle,offsets);}
}
for(const count of [0,1,256])for(const n of [0,8,16,64]){
 const tiles=Array.from({length:count},(_,i)=>({id:String(i),point:[i%7,Math.floor(i/7)*.01,0],u:[1,0,-0],v:[0,0,1],bounds:[-.5,.5,-.5,.5]}));
 const offsets=Array.from({length:n},(_,i)=>shoe[i%shoe.length].slice()),terrain=L.create({tiles});
 for(const y of [-0,0,.1])sample('bounds-signed-zero',terrain,[0,y,0],offsets);
}
const bytes=16+records.reduce((n,r)=>n+8+8*(r.input.length+r.expected.length),0),buffer=Buffer.alloc(bytes);buffer.write('FIKFLR01');buffer.writeUInt32LE(records.length,8);let at=16;
for(const r of records){buffer.writeUInt32LE(r.input.length,at);buffer.writeUInt32LE(r.expected.length,at+4);at+=8;for(const v of [...r.input,...r.expected]){buffer.writeDoubleLE(v,at);at+=8;}}
fs.writeFileSync(path.join(dir,'floor-queries.bin'),buffer);
const literal=v=>Object.is(v,-0)?'-0':String(v),chosen=records.filter((_,i)=>i%Math.ceil(records.length/96)===0).concat(records.slice(-36));
fs.writeFileSync(path.join(dir,'floor-buffer-inputs.js'),'globalThis.floorFixtures=['+chosen.map(r=>'[['+r.input.map(literal).join(',')+'],['+r.expected.map(literal).join(',')+']]').join(',')+'];');
const report={records:records.length,bytes,labels,oracleSha256:crypto.createHash('sha256').update(code.replaceAll('\r\n','\n')).digest('hex'),fixtureSha256:crypto.createHash('sha256').update(buffer).digest('hex')};
fs.writeFileSync(path.join(dir,'capture.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
