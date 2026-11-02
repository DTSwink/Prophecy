// Accepted current tuning through the actual app, then the native adapter.
// No live state writes; each case owns one short-lived Jolt world.
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
const out=process.env.BODYFLIP_PORT_OUTPUT||'Saved/Diagnostics/BodyflipPort20261102';fs.mkdirSync(out,{recursive:true});
const saved=JSON.parse(fs.readFileSync('Content/BodyflipLab/LabSettings.json')).settings;
const event={id:'action',time:.1,enabled:true,jumpPercent:0,spinVersion:2,flip:0,twist:0,attack:'none'};
const base={...saved,trimIn:0,trimOut:2.6,mode:'spaceGym',jumpEvents:[event]};
const cases=[{name:'saved-pike',settings:saved,times:Array.from({length:40},(_,i)=>i*5/60)},
 ...[
  {name:'pike-steering-off',settings:{...saved,pikeSpineAbsorb:false}},
  {name:'pike-front',settings:{...saved,target:[0,2,3]}},
  {name:'pike-back',settings:{...saved,target:[0,2,-3]}},
  {name:'pike-fast-spin',settings:{...saved,jumpEvents:saved.jumpEvents.map(e=>e.enabled&&e.attack==='pike'?{...e,flip:800,twist:400}:e)}}
 ],
 ...['slashL','slashLU','slashRU','sweepKick','KickL','big-throw','small-throw'].map(attack=>({name:attack,settings:{...base,jumpEvents:[{...event,attack}]}})),
 ...['slashL','sweepKick','big-throw','small-throw'].map(attack=>({name:attack+'-twist',settings:{...base,target:[-1,2,-2],jumpEvents:[{...event,attack,twist:360,throwCharge:37}]}})),
 {name:'poses-and-keep',settings:{...base,trimOut:4,jumpEvents:[{...event,pose:'pose1',flip:180,twist:120},{...event,id:'keep',time:.8,pose:'keep',twist:-400},{...event,id:'ignored',time:1.2,enabled:false,pose:'none'},{...event,id:'snatch',time:1.5,pose:'pose2'},{...event,id:'ball',time:2.2,pose:'pose3'},{...event,id:'ninja',time:2.9,pose:'pose4'},{...event,id:'clear',time:3.5,pose:'none'}]},times:Array.from({length:41},(_,i)=>i/10)},
 {name:'authored-world-ray',settings:{...base,jumpEvents:[{...event,attack:'big-throw',twist:160,throwDirection:[-1,.2,1]}]}},
];
const filter=process.argv.find(a=>a.startsWith('--case='))?.slice(7),reports=[];
for(const c of cases.filter(c=>!filter||c.name===filter)){
 c.times||=Array.from({length:27},(_,i)=>i/10);c.playback={time:0,playing:false};
 const input=out+'/'+c.name+'-input.json',output=out+'/'+c.name+'-frames.json';fs.writeFileSync(input,JSON.stringify(c));
 const result=spawnSync(process.execPath,['Labs/BodyflipLab/verify-native-app-parity.mjs'],{encoding:'utf8',timeout:180000,maxBuffer:4e6,env:{...process.env,BODYFLIP_PARITY_FILE:input,BODYFLIP_PARITY_OUTPUT:output}});
 fs.writeFileSync(out+'/'+c.name+'-app.log',result.stdout+'\n'+result.stderr);
 assert.equal(result.status,0,c.name+': '+result.stderr+'\n'+result.stdout);
 const report=JSON.parse(result.stdout);reports.push(report);console.log(JSON.stringify({name:c.name,frames:report.frames,maxPosition:report.maxPosition,maxRotation:report.maxRotation}));
 fs.writeFileSync(out+'/app-parity'+(filter?'-'+filter:'')+'.json',JSON.stringify({passed:true,reports},null,2));
}
assert(reports.length,'No matching cases');
fs.writeFileSync(out+'/current-port-fixture.json',JSON.stringify({cases:reports.map(r=>JSON.parse(fs.readFileSync(out+'/'+r.name+'-frames.json')))}));
