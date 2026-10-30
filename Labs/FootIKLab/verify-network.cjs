'use strict';
const assert=require('assert/strict'),{request}=require('./network.js');
(async()=>{
 let calls=0,signal;
 const hung=async(_,options)=>{calls++;signal=options.signal;return new Promise(()=>{});};
 await assert.rejects(request('/resume',{},'json',20,hung),/Motion generation did not respond/);
 assert.equal(calls,1);assert(signal.aborted);
 await assert.rejects(request('/state',{},'json',20,async()=>({ok:true,json:()=>new Promise(()=>{})})),/Foot IK server did not respond/);
 await assert.rejects(request('/resume',{},'json',500,async()=>({ok:false,status:400,json:async()=>({error:'Missing continuation'})})),/Missing continuation/);
 assert.deepEqual(await request('/state',{},'json',500,async()=>({ok:true,json:async()=>({frame:195})})),{frame:195});
 await assert.rejects(request('/health',{},'json',500,async()=>{throw TypeError('fetch failed');}),/server is unavailable/);
 console.log('5 bounded-request checks pass');
})().catch(error=>{console.error(error);process.exitCode=1;});
