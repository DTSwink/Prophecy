'use strict';
// Inject stale dependency metadata only in a disposable Node process. Neither
// the canonical source nor the real contract is edited during this check.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process'),{pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'../..'),hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),runtime=path.join(root,'Content/FootIKLab/Runtime.js'),receipt=path.join(root,'Content/FootIKLab/Receipt.json'),before=[hash(runtime),hash(receipt)];
const script=`const fs=require('node:fs'),read=fs.readFileSync;fs.readFileSync=function(file,...args){const value=read.call(this,file,...args);if(String(file).endsWith('native-kernel-contract.json')){const c=JSON.parse(value.toString());c.dependencies.brace['slide-arms.js']='deliberately-stale';const s=JSON.stringify(c);return typeof value==='string'?s:Buffer.from(s);}return value;};import(${JSON.stringify(pathToFileURL(path.join(__dirname,'package-runtime.mjs')).href)}).catch(e=>{console.error(e.message);process.exitCode=1;});`;
const child=cp.spawnSync(process.execPath,['-e',script],{cwd:root,encoding:'utf8',windowsHide:true,timeout:30000,maxBuffer:1024*1024});
if(child.error||child.status!==1||!child.stderr.includes('Native brace dependency changed: slide-arms.js'))throw child.error||Error('Stale dependency was not rejected: '+child.stderr);
if(hash(runtime)!==before[0]||hash(receipt)!==before[1])throw Error('Rejected package modified generated artifacts');
const report={passed:true,staleCanonicalDependencyRejected:true,generatedArtifactsUntouched:true};
fs.writeFileSync(path.join(root,'Saved/Diagnostics/FootIKPort20261030/native-kernel-contract.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
