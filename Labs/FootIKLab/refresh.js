/* Reuse a ready scene only while all its served sources predate this page. */
(function(root){
 'use strict';
 function create(files,pageStarted,request=fetch){
  return async function unchanged(){
   if(!Number.isFinite(pageStarted))return false;
   let cursor=0,valid=true;
   // Bound connections: this lab's lightweight HTTP server has a small queue.
   await Promise.all(Array.from({length:4},async()=>{
    while(cursor<files.length&&valid){
     const file=files[cursor++],response=await request(file,{method:'HEAD',cache:'no-store'});
     const modified=Date.parse(response.headers.get('Last-Modified'));
     // HTTP dates have one-second precision. An edit in the navigation's
     // second is ambiguous, so conservatively reload rather than retain it.
     if(!response.ok||!Number.isFinite(modified)||modified>=Math.floor(pageStarted/1000)*1000)valid=false;
    }
   }));
   return valid;
  };
 }
 const api={create};if(typeof module!=='undefined')module.exports=api;else root.FootRefresh=api;
})(globalThis);
