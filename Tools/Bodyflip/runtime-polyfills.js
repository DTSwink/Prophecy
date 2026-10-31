/* Compatibility only for the Windows JSRT engine; algorithms are unchanged. */
this.globalThis=this;
(function(){
if(!Array.prototype.at)Object.defineProperty(Array.prototype,'at',{value:function(index){index=Math.trunc(index)||0;return this[index<0?this.length+index:index];},configurable:true,writable:true});
if(!Array.prototype.flat)Object.defineProperty(Array.prototype,'flat',{value:function(depth){depth=depth===undefined?1:Math.max(0,Math.trunc(depth));var out=[];for(var i=0;i<this.length;i++)if(i in this){var v=this[i];if(depth>0&&Array.isArray(v))out.push.apply(out,v.flat(depth-1));else out.push(v);}return out;},configurable:true,writable:true});
if(!Array.prototype.flatMap)Object.defineProperty(Array.prototype,'flatMap',{value:function(f,self){return this.map(f,self).flat();},configurable:true,writable:true});
if(!Object.fromEntries)Object.fromEntries=function(entries){var out={};for(var entry of entries)out[entry[0]]=entry[1];return out;};
if(!String.prototype.replaceAll)Object.defineProperty(String.prototype,'replaceAll',{value:function(pattern,replacement){return this.split(pattern).join(replacement);},configurable:true,writable:true});
})();
