/* Native compatibility with V8 13.6.233.17 Math.hypot operation order.
 * Ported from src/builtins/math.tq, Copyright 2019 the V8 project authors.
 * V8 source is distributed under its BSD-style LICENSE:
 * https://chromium.googlesource.com/v8/v8/+/refs/tags/13.6.233.17/LICENSE
 * Source: https://chromium.googlesource.com/v8/v8/+/refs/tags/13.6.233.17/src/builtins/math.tq
 * This native-runtime shim does not change the canonical lab implementation.
 */
(function(){
'use strict';
function hypot(){
 var count=arguments.length;if(count===0)return 0;
 var a=Math.abs(arguments[0]);if(count===1)return a;
 var b=Math.abs(arguments[1]),maximum;
 if(count===2){
  if(a===Infinity||b===Infinity)return Infinity;
  maximum=Math.max(a,b);if(maximum!==maximum)return NaN;if(maximum===0)return 0;
  return Math.sqrt((a/maximum)*(a/maximum)+(b/maximum)*(b/maximum))*maximum;
 }
 if(count===3){
  var c=Math.abs(arguments[2]);if(a===Infinity||b===Infinity||c===Infinity)return Infinity;
  maximum=Math.max(Math.max(a,b),c);if(maximum!==maximum)return NaN;if(maximum===0)return 0;
  var powerA=(a/maximum)*(a/maximum),powerB=(b/maximum)*(b/maximum);
  var compensation=(powerA+powerB)-powerA-powerB,powerC=(c/maximum)*(c/maximum)-compensation;
  return Math.sqrt(powerA+powerB+powerC)*maximum;
 }
 var values=new Array(count),hasNaN=false;maximum=0;
 for(var i=0;i<count;i++){var value=+arguments[i];if(value!==value)hasNaN=true;else{value=Math.abs(value);values[i]=value;if(value>maximum)maximum=value;}}
 if(maximum===Infinity)return Infinity;if(hasNaN)return NaN;if(maximum===0)return 0;
 var sum=0,correction=0;
 for(var j=0;j<count;j++){var n=values[j]/maximum,summand=n*n-correction,preliminary=sum+summand;correction=(preliminary-sum)-summand;sum=preliminary;}
 return Math.sqrt(sum)*maximum;
}
Object.defineProperty(Math,'hypot',{value:hypot,configurable:true,writable:true});
})();
