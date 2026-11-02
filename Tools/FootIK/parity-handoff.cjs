'use strict';
// Generate whole-app continuation requests without changing the viewer or NN.
// The matching canonical NN responses are supplied by the offline NN exporter.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto');
const {root,cases}=require('./parity-cases.cjs'),K=require('../../Labs/FootIKLab/footik.js'),H=require('../../Labs/FootIKLab/handoff.js');
const parents=require('../../Labs/FootIKLab/data/rig.json').parents;
const folder=path.join(root,'Saved/Diagnostics/FootIKPort20261030/handoff');fs.mkdirSync(folder,{recursive:true});
if(process.argv.includes('--record')){
 const files=JSON.parse(fs.readFileSync(path.join(folder,'requests.json'))).cases,output=path.join(root,'Tools/FootIK/parity-fixtures');
 const records=[];for(const file of files){const input=JSON.parse(fs.readFileSync(path.join(folder,file.name+'.input.json')));input.handoffReply=JSON.parse(fs.readFileSync(path.join(folder,file.response)));delete input.parents;const bytes=zlib.gzipSync(Buffer.from(JSON.stringify(input)),{level:9});fs.writeFileSync(path.join(output,file.name+'.json.gz'),bytes);records.push({name:file.name,bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});}
 fs.writeFileSync(path.join(output,'handoff-manifest.json'),JSON.stringify({schema:'footik-handoff-replay-inputs-v1',records},null,2));console.log(JSON.stringify(records));process.exit(0);
}
const selected=cases().filter(c=>/^(walk|run)-(stairs|down|uneven)$/.test(c.name)),manifest=[];
for(const item of selected){
 const run=K.decode(item.input.source,parents),model=K.prepare(run,item.input.settings),plan=H.requestFor(model,run),name='app-'+item.name;
 if(!plan)throw Error('No handoff for required case '+name);
 const requestFile=name+'.request.json';fs.writeFileSync(path.join(folder,requestFile),JSON.stringify(plan.request));
 fs.writeFileSync(path.join(folder,name+'.input.json'),JSON.stringify({...item.input,handoff:true,parents}));
 manifest.push({name,request:requestFile,response:name+'.response.json',index:plan.index,time:plan.time,frames:plan.request.frames});
}
fs.writeFileSync(path.join(folder,'requests.json'),JSON.stringify({schema:'footik-handoff-inputs-v1',cases:manifest},null,2));console.log(JSON.stringify(manifest));
