/* Monotone recording-time remap. Four draggable interior points; fixed ends. */
(function(root){
'use strict';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const linear=()=>[.2,.4,.6,.8].map(x=>[x,x]);
function sanitize(value){
 if(!Array.isArray(value)||value.length!==4||value.some(p=>!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite)))return linear();
 const result=[];let x=0,y=0;
 for(let i=0;i<4;i++){x=clamp(value[i][0],x+.01,1-(4-i)*.01);y=clamp(value[i][1],y,1);result.push([x,y]);}return result;
}
function prepare(value){
 const points=[[0,0],...sanitize(value),[1,1]],h=[],d=[],m=[];
 for(let i=0;i<5;i++){h[i]=points[i+1][0]-points[i][0];d[i]=(points[i+1][1]-points[i][1])/h[i];}
 m[0]=d[0];m[5]=d[4];
 for(let i=1;i<5;i++){const w1=2*h[i]+h[i-1],w2=h[i]+2*h[i-1];m[i]=d[i-1]*d[i]<=0?0:(w1+w2)/(w1/d[i-1]+w2/d[i]);}
 return {points,h,m,identity:points.every(([x,y])=>x===y)};
}
function sample(curve,x){
 x=clamp(x,0,1);if(curve.identity||x===0||x===1)return x;
 const {points:p,h,m}=curve;let i=0;while(i<4&&x>p[i+1][0])i++;
 const t=(x-p[i][0])/h[i],t2=t*t,t3=t2*t;
 return clamp((2*t3-3*t2+1)*p[i][1]+(t3-2*t2+t)*h[i]*m[i]+(-2*t3+3*t2)*p[i+1][1]+(t3-t2)*h[i]*m[i+1],p[i][1],p[i+1][1]);
}
function time(curve,t,start,end){if(curve.identity||t<=start||t>=end||end<=start)return t;return start+(end-start)*sample(curve,(t-start)/(end-start));}
const api={linear,sanitize,prepare,sample,time};if(typeof module!=='undefined')module.exports=api;else root.Retime=api;
})(globalThis);
