const assert=require('node:assert/strict'),{create}=require('./refresh.js');
(async()=>{
 const page=Date.UTC(2026,9,27,10,0,0)+500,old=new Date(page-2000).toUTCString();
 const files=Array.from({length:20},(_,i)=>'file'+i);let active=0,maxActive=0,requests=0;
 const read=async()=>{active++;maxActive=Math.max(maxActive,active);requests++;await new Promise(r=>setTimeout(r,1));active--;return new Response(null,{headers:{'Last-Modified':old}});};
 assert(await create(files,page,read)());assert.equal(requests,20);assert.equal(maxActive,4);
 const response=date=>async()=>new Response(null,{headers:{'Last-Modified':date}});
 assert(!await create(files,page,response(new Date(page+2000).toUTCString()))());
 assert(!await create(files,page,response(new Date(page).toUTCString()))());
 assert(!await create(files,page,async()=>new Response(null))());
 assert(!await create(files,page,async()=>new Response(null,{status:404,headers:{'Last-Modified':old}}))());
 assert(!await create(files,NaN,read)());
 await assert.rejects(create(files,page,async()=>{throw Error('offline');})());
 console.log('Refresh guards: unchanged, changed, ambiguous, missing, offline and bounded concurrency passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
