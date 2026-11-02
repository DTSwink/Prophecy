'use strict';
// Saved-only candidate packaging. Production packaging is owned by package-runtime.mjs.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),root=path.resolve(__dirname,'../..');
const out=path.join(root,'Saved/Diagnostics/FootIKPort20261030/native-v8'),runtime=fs.readFileSync(path.join(root,'Content/FootIKLab/Runtime.js'),'utf8'),hypot=fs.readFileSync(path.join(__dirname,'deterministic-math.js'),'utf8');
if(!runtime.includes(hypot))throw Error('Expected exact hypot shim once');
const wasm=fs.readFileSync(path.join(out,'trig/trig.js'),'utf8'),result=wasm+runtime.replace(hypot,'');
fs.writeFileSync(path.join(out,'RuntimeV8.js'),result);console.log(JSON.stringify({bytes:result.length,sha256:crypto.createHash('sha256').update(result).digest('hex')}));
