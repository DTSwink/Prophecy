/* Bounded local requests, including response-body reads. No automatic retries
 * of mutations: a timeout must not duplicate state or inference work. */
(function(root){
 'use strict';
 async function request(url,options={},read='json',timeoutMs=8000,transport=fetch){
  const controller=new AbortController();let timer;
  const label=String(url).includes('/resume')?'Motion generation':'Foot IK server';
  const work=(async()=>{const response=await transport(url,{...options,signal:controller.signal});
   const value=read==='response'?response:await response[read]();
   if(!response.ok)throw Error(value?.error||`${label}: HTTP ${response.status}`);
   return value;
  })();
  const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error(`${label} did not respond in ${Math.round(timeoutMs/1000)}s. Refresh to retry.`));},timeoutMs);});
  try{return await Promise.race([work,timeout]);}
  catch(error){if(error instanceof TypeError)throw Error('Foot IK server is unavailable. Your saved scene is retained.');throw error;}
  finally{clearTimeout(timer);}
 }
 const api={request,json:(url,options={},ms=8000)=>request(url,options,'json',ms),head:(url,options={})=>request(url,{...options,method:'HEAD'},'response',5000)};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.FootHTTP=api;
})(globalThis);
