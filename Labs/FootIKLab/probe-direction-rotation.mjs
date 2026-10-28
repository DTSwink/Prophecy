import fs from 'node:fs';
import vm from 'node:vm';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),{audit}=require('./motion-audit.js'),rig=JSON.parse(fs.readFileSync(new URL('data/rig.json',import.meta.url)));
const source=fs.readFileSync(new URL('footik.js',import.meta.url),'utf8'),key='const held=releaseRotation(natural,l,released);';
if(!source.includes(key))throw Error('Core anchor moved; inspect before instrumenting.');
const rows=[];
for(const bypass of [false,true]){
 const sandbox={require,module:{exports:{}},console};vm.runInNewContext(bypass?source.replace(key,'const held=natural;'):source,sandbox);const K=sandbox.module.exports;
 for(const [gait,direction,side,frame] of [['walk','left',0,82],['walk','backward',1,196],['run','left',0,98],['run','backward',1,84]]){
  const data=JSON.parse(fs.readFileSync(new URL('.nn-cache/directional-'+gait+'-'+direction+'.json',import.meta.url))),run=K.decode(data,rig.parents),model=K.prepare(run,{gait,direction,phase:.21,terrain:'stairs',height:16,depth:35,steps:12,clearance:1}),a=audit({run,model,options:{geometry:false}});
  rows.push({bypass,gait,direction,side:['L','R'][side],frame,specific:a.rows[frame*2].feet[side],metrics:model.metrics,summary:a.summary[['L','R'][side]]});
 }
}
const result={sourceSha256:crypto.createHash('sha256').update(source).digest('hex'),change:'Only in-memory bypass of final free-foot releaseRotation, with original full-shoe clearance still active',rows};
fs.writeFileSync(new URL('snapshots/direction-rotation-probe.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(rows.map(r=>({bypass:r.bypass,gait:r.gait,direction:r.direction,frame:r.frame,ankle:r.specific.ankleNNError,footStep:r.summary.footStep,pen:r.metrics.maxPenetration,pins:r.metrics.pins}))));
