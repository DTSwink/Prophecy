import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),S=require('./support.js'),rig=JSON.parse(fs.readFileSync(new URL('data/rig.json',import.meta.url)));
const source=fs.readFileSync(new URL('footik.js',import.meta.url),'utf8'),records=[];
const hook=`let chosen=roll.sample(natural);
    if(settings.direction==='backward'&&side===0&&i>=224&&i<=265){
     const goalProbe=softReach(length(sub(chosen.foot,hip)),current.reach,weights[i]),list=[];
     for(let d=-75;d<=75;d+=2.5){const r=roll.sample(natural+d),dist=length(sub(r.foot,hip));list.push({extra:d,pitch:roll.pitch-r.angle,distance:dist,goal:goalProbe,valid:r.valid,clear:terrain.floorFor(r.foot,geometry(raw[i],current,r.rotation))<=r.foot[1]+1e-6,foot:r.foot});}
     globalThis.auditProbe({frame:i/2,goal:goalProbe,reach:current.reach,natural,sourcePitch,hip,initial:chosen.foot,candidates:list});
    }`;
if(!source.includes('let chosen=roll.sample(natural);'))throw Error('Core probe anchor moved; inspect before instrumenting.');
const sandbox={require,module:{exports:{}},console,auditProbe:r=>records.push(r)};
vm.runInNewContext(source.replace('let chosen=roll.sample(natural);',hook),sandbox,{filename:'footik-probe-only.js'});
const K=sandbox.module.exports,data=JSON.parse(fs.readFileSync(new URL('.nn-cache/directional-walk-backward.json',import.meta.url))),run=K.decode(data,rig.parents);
K.prepare(run,{gait:'walk',direction:'backward',phase:.21,terrain:'stairs',height:16,depth:35,steps:12,clearance:1});
const out=records.filter(r=>r.frame%2===0||r.frame===132.5).map(r=>{const candidates=r.candidates.filter(c=>c.valid&&c.clear),bestSign=sign=>candidates.filter(c=>Math.sign(c.extra)===sign).sort((a,b)=>a.distance-b.distance)[0],satisfy=candidates.filter(c=>c.distance<=r.goal).sort((a,b)=>Math.abs(a.extra)-Math.abs(b.extra))[0];return{frame:r.frame,sourcePitch:r.sourcePitch,goal:r.goal,reach:r.reach,naturalDistance:R.length(R.sub(r.initial,r.hip)),bestNegative:bestSign(-1),bestPositive:bestSign(1),minimumExtraSatisfying:satisfy||null};});
fs.writeFileSync(new URL('snapshots/backward-roll-probe.json',import.meta.url),JSON.stringify(out,null,2));console.log(JSON.stringify(out));
