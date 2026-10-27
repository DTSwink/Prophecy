(function(root){
'use strict';
const copy=v=>structuredClone(v),equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
class History {
 constructor(settings,saved={}){this.current=copy(settings);this.undoStack=copy(Array.isArray(saved.undo)?saved.undo:[]).filter(v=>v&&typeof v==='object'&&!Array.isArray(v));this.redoStack=copy(Array.isArray(saved.redo)?saved.redo:[]).filter(v=>v&&typeof v==='object'&&!Array.isArray(v));this.group=false;this.recorded=false;this.bound();}
 bound(){this.undoStack=this.undoStack.slice(-100);this.redoStack=this.redoStack.slice(-100);while(JSON.stringify([this.undoStack,this.redoStack]).length>1024*1024){if(this.undoStack.length)this.undoStack.shift();else if(this.redoStack.length)this.redoStack.shift();else break;}}
 begin(){if(!this.group){this.group=true;this.recorded=false;}}
 end(){this.group=false;this.recorded=false;}
 record(settings){if(equal(this.current,settings))return false;if(!this.group||!this.recorded){this.undoStack.push(copy(this.current));this.redoStack=[];this.recorded=true;this.bound();}this.current=copy(settings);return true;}
 move(redo=false){this.end();const source=redo?this.redoStack:this.undoStack,destination=redo?this.undoStack:this.redoStack;if(!source.length)return null;destination.push(copy(this.current));this.current=source.pop();this.bound();return copy(this.current);}
 rebase(settings){this.current=copy(settings);}
 pack(){return {version:1,undo:copy(this.undoStack),redo:copy(this.redoStack)};}
}
// Explicit, guarded one-time repairs survive a stale open window saving on
// Refresh. Receipts live outside history so undo cannot reapply a repair.
function repairState(input,repairs=[]){
 const state=copy(input);let changed=false;
 const visit=(snapshot,scene)=>{for(const repair of repairs){if(scene!==repair.scene||(snapshot.repairs||[]).includes(repair.id))continue;
  if(repair.clearHandKeys){
   const keys=snapshot.settings?.vanilla?.[repair.clip]?.keys;
   if(equal(keys,repair.expectedKeys)){
    const history=new History(snapshot.settings,snapshot.history);snapshot.settings.vanilla[repair.clip].keys=[];history.record(snapshot.settings);snapshot.history=history.pack();
   }
  }else if(repair.undoSteps){
   if(equal(snapshot.settings,repair.expectedSettings)&&(snapshot.history?.undo?.length||0)>=repair.undoSteps){const history=new History(snapshot.settings,snapshot.history);for(let i=0;i<repair.undoSteps;i++)snapshot.settings=history.move();snapshot.history=history.pack();}
  }else{const keys=snapshot.settings?.vanilla?.[repair.clip]?.keys,index=keys?.findIndex(k=>k.frame===repair.frame&&equal(k.rotation,repair.expectedRotation));if(index>=0)keys.splice(index,1);}
  snapshot.repairs=[...(snapshot.repairs||[]),repair.id];changed=true;
 }};
 visit(state,state.scenes?.active||'original');for(const item of state.scenes?.items||[])visit(item.state,item.id);
 return {state,changed};
}
const api={History,repairState};if(typeof module!=='undefined')module.exports=api;else root.ThrowHistory=api;
})(globalThis);
