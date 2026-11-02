'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),P=require('./live-stair-planner.cjs'),L=require('./live-terrain.cjs'),K=require('../../Labs/FootIKLab/footik.js');
const input=JSON.parse(fs.readFileSync('Saved/Diagnostics/FootIKPort20261030/walk-stairs.input.json')),source=input.source,settings=K.sanitize(input.settings),terrain={rootRows:source.roots.map((p,i)=>({time:i/30,position:[p[0],.5,p[2]]})),tiles:[{id:'actor:box:top',point:[0,.5,0],u:[1,0,0],v:[0,0,1],bounds:[-20,20,-20,30],shaped:true}]};
async function main(){
 const run=K.decode(source,input.parents),world=L.create(terrain),root=L.rootSampler(terrain.rootRows),host={terrain:world,origin:[0,0,0],rootAtTime:root.at,travelAt:root.direction,speedAt:root.speed,headingAt:t=>K.rootHeading(run,t,settings),influence:()=>0};
 let wall=performance.now(),cpu=process.cpuUsage();const baseline=K.prepare(run,settings,host);const before={ms:performance.now()-wall,cpuMs:Object.values(process.cpuUsage(cpu)).reduce((a,b)=>a+b,0)/1000};
 wall=performance.now();cpu=process.cpuUsage();const planner=P.create({...input,terrain,handoff:false});await planner.plan();const after={ms:performance.now()-wall,cpuMs:Object.values(process.cpuUsage(cpu)).reduce((a,b)=>a+b,0)/1000};
 for(let i=0;i<baseline.frames.length;i++)assert.deepEqual(planner.frame(i),baseline.frames[i]);
 const report={frames:baseline.frames.length,exact:true,before,after,cpuRatio:before.cpuMs/after.cpuMs,wallRatio:before.ms/after.ms};fs.writeFileSync('Saved/Diagnostics/FootIKPort20261030/live-flat-fastpath.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
