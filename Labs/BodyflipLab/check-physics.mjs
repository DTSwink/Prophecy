import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);globalThis.Recovery=require('./recovery.js');
const C=require('./core.js'),R=globalThis.Recovery,m=JSON.parse(fs.readFileSync(new URL('./data/manifest.json',import.meta.url)));
const {createPhysics}=await import('./physics.mjs');
const idle=C.poseFromShared(m),base=C.centerPose(idle,idle.q[1]);
const p=await createPhysics(m,base);p.reset(base);
for(let t=0;t<480;t++)p.step(C.centerPose(idle,R.qm(C.orientation(t/240*120,t/240*30,0),idle.q[1])),1/240);
console.log(JSON.stringify(p.diagnostics(),null,2));p.dispose();
