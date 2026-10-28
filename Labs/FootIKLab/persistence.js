/* Save user edits, not entire stale tabs. No inference/render dependency. */
(function (root) {
 'use strict';
 const sections=['settings','camera','playback'];
 const clone=value=>JSON.parse(JSON.stringify(value));
 function create(initial,read,write){
  let captured=clone(initial),pending={},serial=0,timer=null;
  const client=globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random()}`;
  function capture(){
   const next=clone(read());
   for(const section of sections)for(const [key,value] of Object.entries(next[section]||{})){
    if(JSON.stringify(value)!==JSON.stringify(captured[section]?.[key])){
     (pending[section]||={})[key]={value,serial:++serial};
    }
   }
   captured=next;
  }
  async function flush(){
   clearTimeout(timer);timer=null;capture();
   if(!Object.keys(pending).length)return;
   const sequence=serial,changes={};
   for(const [section,fields] of Object.entries(pending)){
    changes[section]=Object.fromEntries(Object.entries(fields).map(([key,item])=>[key,item.value]));
   }
   await write({client,sequence,changes});
   for(const [section,fields] of Object.entries(pending)){
    for(const [key,item] of Object.entries(fields))if(item.serial<=sequence)delete fields[key];
    if(!Object.keys(fields).length)delete pending[section];
   }
  }
  function save(onError){capture();clearTimeout(timer);timer=setTimeout(()=>flush().catch(onError),200);}
  // Refresh has already flushed this tab, then adopted the server snapshot.
  // Do not publish those unchanged fields back over another tab's next edit.
  function accept(value){captured=clone(value);}
  return {save,flush,accept};
 }
 if(typeof module!=='undefined')module.exports={create};else root.FootPersistence={create};
})(globalThis);
