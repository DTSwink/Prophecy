import fs from 'node:fs';import{spawnSync}from'node:child_process';
const base={mode:'spaceGym',motion:'kinematic',aim:true,ramps:false,surfaceIK:false,trimOut:1.4,target:[-1,1,-2],spinLag:.6};
const cases=[
{name:'sweep mixed spin aimed behind',settings:{...base,jumpEvents:[{id:'a',time:.1,jumpPercent:0,attack:'sweepKick',flip:150,twist:-60,spinVersion:2}]}},
...[37,.37].map(charge=>({name:'small throw '+charge+' percent mixed spin aimed behind',settings:{...base,jumpEvents:[{id:'a',time:.1,jumpPercent:0,attack:'small-throw',throwCharge:charge,flip:150,twist:-60,spinVersion:2}]}})),
{name:'idle foot push with surface correction',times:[0,.1,.2,.3,.4,.5],settings:{...base,mode:'idle',aim:false,trimOut:.5,platforms:[{id:'floor',position:[0,-.2,0],size:[10,.4,20],rotation:[0,0,0,1]}],jumpEvents:[{id:'a',time:.1,jumpPercent:35,attack:'none',flip:120,twist:30,spinVersion:2}]}}
];let ok=true;const results=[];
for(const fixture of cases){fixture.playback={time:0,playing:false};const r=spawnSync(process.execPath,['Labs/BodyflipLab/verify-native-app-parity.mjs'],{env:{...process.env,BODYFLIP_PARITY_FIXTURE:JSON.stringify(fixture)},encoding:'utf8',timeout:180000,maxBuffer:5000000});results.push({name:fixture.name,fixture,status:r.status,stdout:r.stdout,stderr:r.stderr});console.log(r.stdout||r.stderr);if(r.status!==0){console.error(r.stderr);ok=false;}}
fs.writeFileSync('Saved/Diagnostics/BodyflipPort20261030/app-parity.json',JSON.stringify(results,null,2));if(!ok)process.exitCode=1;
