'use strict';
// Keep only independent NN inputs/replies needed to reproduce native parity.
// Do not archive old solved poses, caches, gzip frame batches or UI sessions.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib'),crypto=require('node:crypto');
const {root,cases}=require('./parity-cases.cjs'),folder=path.join(__dirname,'parity-fixtures');
fs.mkdirSync(folder,{recursive:true});
const manifest={schema:'footik-recorded-policy-input-v1',note:'Recorded policy inputs/replies, not baked solver output. Regenerate all pose oracles from current lab source.',cases:[]};
for(const item of cases().filter(c=>c.input.policySteps)){
 const bytes=Buffer.from(JSON.stringify(item.input)),gzip=zlib.gzipSync(bytes,{level:9}),file=item.name+'.json.gz';
 fs.writeFileSync(path.join(folder,file),gzip);
 const original=item.originalDependency||item.dependency;
 manifest.cases.push({name:item.name,file,original,originalSha256:fs.existsSync(path.join(root,original))?crypto.createHash('sha256').update(fs.readFileSync(path.join(root,original))).digest('hex'):null,sha256:crypto.createHash('sha256').update(gzip).digest('hex'),bytes:gzip.length,policySteps:item.input.policySteps.length,endTime:item.input.endTime,source:item.input.source.source});
}
fs.writeFileSync(path.join(folder,'manifest.json'),JSON.stringify(manifest,null,2));
console.log(JSON.stringify({cases:manifest.cases.length,bytes:manifest.cases.reduce((n,c)=>n+c.bytes,0),folder}));
