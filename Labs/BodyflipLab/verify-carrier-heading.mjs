// Carrier metadata must survive seeks without changing authored animation data.
// Uses synthetic contacts and in-memory runtimes; no server, assets or outputs written.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),K=require('./capsule.js'),S=require('./support.js');
let checks=0;
const check=(ok,label)=>{assert(ok,label);checks++;};
const pose=(root,rotation)=>({points:[root,R.add(root,[0,1,0])],q:[rotation,rotation],axes:[R.toAxes(rotation),R.toAxes(rotation)]});
const floor=S.ground(100),initialYaw=Math.PI/3,landedYaw=-Math.PI*.9;
const source=t=>{const root=[0,2-4.905*t*t,0];return {root,pose:pose(root,R.qexp([t,4*t,.3])),phase:'FALL',airTime:t,vy:-9.81*t};};
const options={surfaces:[floor],speed:0,phase:'IDLE',gait:()=>pose([0,0,0],[0,0,0,1]),fallPose:()=>pose([0,0,0],[0,0,0,1]),headingAt:()=>R.qexp([0,landedYaw,0])};
const original=K.track(source,options),track=K.track(source,{...options,initialYaw});
for(const time of [0,.2,.4,.8,1]){
 const before=original.sample(time),after=track.sample(time);
 assert.deepEqual(after.pose,before.pose);assert.deepEqual(after.root,before.root);checks+=2;
 check(Math.abs(after.capsule.yaw-(after.capsule.landed?landedYaw:initialYaw))<1e-12,'Carrier follows the command until an actual backward landing');
}
check(track.landings.length===1,'The fixture includes a real surface landing');
const snapshots=new Map([0,.2,.4,.8,1].map(t=>[t,JSON.stringify(track.sample(t))]));
for(const time of [1,.2,.8,0,.4,1])check(JSON.stringify(track.sample(time))===snapshots.get(time),'Reverse seeks retain the exact carrier and pose');
const inherited=track.sample(1).capsule.yaw;
const airborne=K.track(t=>{const root=[0,4,t];return {root,pose:pose(root,R.qexp([2*t,7*t,t])),phase:'RISE',airTime:1,vy:0};},{...options,start:1,surfaces:[],initialYaw:inherited});
for(const time of [1,1.5,1.1])check(Math.abs(airborne.sample(time).capsule.yaw-landedYaw)<1e-12,'A subsequent airborne segment retains the last landing heading');

// Compare fresh canonical modules against the currently packaged runtime before
// publishing a new package. After packaging this remains a source/package check.
const base=path.resolve('Labs/BodyflipLab'),sources=new Map();
function gather(file){file=path.resolve(file);if(sources.has(file))return;const code=fs.readFileSync(file,'utf8');sources.set(file,code);for(const match of code.matchAll(/require\(['"]([^'"]+)['"]\)/g))if(match[1].startsWith('.')){const child=path.resolve(path.dirname(file),match[1]);if(fs.existsSync(child))gather(child);}}
for(const file of ['flight.js','attack-aim.js','idle.js','throw-attack.js','target-rig.js'])gather(path.join(base,file));
const id=file=>path.relative(path.resolve('Labs'),file).replaceAll('\\','/');
const factories=[...sources].map(([file,code])=>JSON.stringify(id(file))+':function(module,exports,require){\n'+code+'\n}');
const loader=`globalThis.BodyflipRequire=(function(){const factories={${factories.join(',\n')}},cache={};return function load(id){if(cache[id])return cache[id].exports;const m={exports:{}};cache[id]=m;factories[id](m,m.exports,name=>{const p=id.split('/');p.pop();for(const part of name.split('/')){if(part==='..')p.pop();else if(part!=='.')p.push(part);}return load(p.join('/'));});return m.exports;};})();`;
const fresh=fs.readFileSync('Tools/FootIK/v8-trig.js','utf8')+'\n'+loader+'\n'+fs.readFileSync('Tools/Bodyflip/runtime-adapter.js','utf8');
function runtime(code){const context=vm.createContext({console,performance,structuredClone,__bodyflipAttack:id=>fs.readFileSync('Content/BodyflipLab/Attacks/'+id+'.json','utf8'),__bodyflipNN:()=>{throw Error('Unexpected NN request in metadata fixture');}});vm.runInContext(code,context);return input=>JSON.parse(vm.runInContext('BodyflipNative.command('+JSON.stringify(JSON.stringify(input))+')',context));}
const previous=runtime(fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8')),current=runtime(fresh);
for(const call of [previous,current])call({op:'assets',value:JSON.parse(fs.readFileSync('Content/BodyflipLab/Assets.json','utf8'))});
const cases=[
 {mode:'idle',startYaw:0,times:[0,.2,0,.3]},
 {mode:'idle',startYaw:90,times:[0,.2,.1]},
 {mode:'spaceGym',startYaw:-45,times:[0,.15,.4,.2],jumpEvents:[{id:'spin',time:.1,jumpPercent:0,flip:180,twist:90,spinVersion:2}]},
 {mode:'spaceGym',startYaw:180,times:[0,.3,.8,1.2,.4],jumpEvents:[{id:'throw',time:.1,jumpPercent:0,attack:'big-throw',flip:0,twist:0,spinVersion:2}]}
];
let exactPackets=0;
for(const fixture of cases){
 const settings={motion:'kinematic',aim:false,ramps:false,surfaceIK:false,trimOut:Math.max(...fixture.times),jumpEvents:[],...fixture};delete settings.times;
 for(const call of [previous,current])call({op:'start',settings,horizon:settings.trimOut});
 for(const time of fixture.times){const before=previous({op:'sample',time}),after=current({op:'sample',time});check(Math.abs(after.heading-fixture.startYaw*Math.PI/180)<1e-12,'Native packet reports commanded carrier yaw');delete before.heading;delete after.heading;assert.deepEqual(after,before,'All pose/root/velocity/event/projectile fields remain exact');checks++;exactPackets++;}
}
console.log(JSON.stringify({passed:true,checks,exactPackets,landing:track.landings[0].time}));
