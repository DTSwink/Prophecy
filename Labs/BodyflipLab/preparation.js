/* Cooperative preparation. Numerical work and its order are unchanged. */
(function(root){
'use strict';
let active=null,held=0;
function checkpoint(){if(!held&&active&&performance.now()>=active.deadline)throw active;}
async function run(operation,cancelled=()=>false){
 const job={deadline:0};
 for(;;){
  if(cancelled())return null;
  const previous=active;active=job;job.deadline=performance.now()+12;
  try{return operation();}catch(error){if(error!==job)throw error;}
  finally{active=previous;}
  await new Promise(resolve=>setTimeout(resolve,0));
 }
}
function hold(){held++;return ()=>{held--;};}
const api={checkpoint,run,hold};if(typeof module!=='undefined')module.exports=api;else root.BodyflipPreparation=api;
})(globalThis);
