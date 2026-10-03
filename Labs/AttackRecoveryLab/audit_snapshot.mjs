import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js');
const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'playwright');
const saved=JSON.parse(await fs.readFile('snapshots/snapshot_0002.json'));
const manifest=JSON.parse(await fs.readFile('data/manifest.json'));
const clip=manifest.clips.find(c=>c.name===saved.attack),meta=clip.variants.find(v=>v.id===saved.variant);
const bytes=await fs.readFile(meta.file),model=R.prepare(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length),clip,manifest.names,manifest.parents);
const settings=JSON.parse(await fs.readFile('frozen/settings.json'));
settings.harnessBranch='standard';settings.preferences.variantType='easy';settings.preferences.startMirrored=false;
const browser=await chromium.launch({headless:true,executablePath:process.env.HARNESS_CHROMIUM_EXECUTABLE,args:['--use-angle=swiftshader']});
try{
 const context=await browser.newContext();
 await context.route('**/*',async route=>{const url=new URL(route.request().url());if(url.origin!=='http://127.0.0.1:8817')return route.abort();if(url.pathname.endsWith('/app-settings'))return route.fulfill({json:{ok:true,initialized:true,...settings}});if(/\/(app-view|app-views|app-control|desktop-view|app-revision|desktop-session)/.test(url.pathname)||route.request().method()!=='GET')return route.fulfill({json:{ok:true,commands:[],views:[]}});return route.continue();});
 const page=await context.newPage();await page.goto('http://127.0.0.1:8817/frozen/source.html?difficulty=easy');await page.waitForFunction(()=>window.finalHarnessStandalone?.ready());
 const result=await page.evaluate(({attack,target,time})=>{finalHarnessStandalone.configureAuditCase({clipName:attack,targetWorldM:target,difficulty:'easy',startMirrored:false,frame:0});const integers=finalHarnessStandalone.visibleTrajectoryCapture();const samples=[22,22.25,22.5,22.75,23,23.25,23.5,time*30,23.75,24];const fractional=finalHarnessStandalone.visibleTrajectoryCapture(samples);return {integers,fractional,samples};},{attack:saved.attack,target:saved.target,time:saved.time});
 const f32b=a=>Buffer.from(Float32Array.from(a).buffer);
 const regenerated=Buffer.concat([f32b(result.integers.points),f32b(result.integers.axes)]);
 const angular=(a,b)=>R.length(R.qlog(R.qm(R.qinv(R.fromAxes(a)),R.fromAxes(b))))*180/Math.PI;
 const rows=result.samples.map((frame,f)=>{const ours=R.sample(model,frame/meta.fps,saved.controls),refAxes=Array.from({length:26},(_,j)=>[0,1,2].map(k=>result.fractional.axes.slice((f*26+j)*9+k*3,(f*26+j)*9+k*3+3)));return {frame,handAngleErrorDeg:angular(ours.axes[14],refAxes[14]),forearmAngleErrorDeg:angular(ours.axes[13],refAxes[13]),sourceHandAxes:refAxes[14],labHandAxes:ours.axes[14]};});
 const report={snapshot:'snapshot_0002',attack:saved.attack,variant:saved.variant,frame:saved.time*meta.fps,sourceIntegerBytesMatch:regenerated.equals(bytes),sourceIntegerSha:crypto.createHash('sha256').update(regenerated).digest('hex'),savedSha:meta.sha256,rows};
 await fs.writeFile(process.argv[2]||'audit-snapshot-0002-current.json',JSON.stringify(report,null,2));
 console.log(JSON.stringify({...report,rows:rows.map(({sourceHandAxes,labHandAxes,...r})=>r)},null,2));
}finally{await browser.close();}
