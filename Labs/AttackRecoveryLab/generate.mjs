// Export a bounded set of exact displayed Easy poses from the frozen harness.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.HARNESS_PLAYWRIGHT_MODULE || 'playwright');
const root = path.dirname(fileURLToPath(import.meta.url));
const origin = 'http://127.0.0.1:8817';
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const sourceReceipt = JSON.parse(await fs.readFile(path.join(root, 'frozen/receipt.json')));
const settings = JSON.parse(await fs.readFile(path.join(root, 'frozen/settings.json')));
settings.harnessBranch = 'standard';
settings.preferences.variantType = 'easy';
settings.preferences.startMirrored = false;
const browser = await chromium.launch({headless:true,
  executablePath:process.env.HARNESS_CHROMIUM_EXECUTABLE,
  args:['--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--use-angle=swiftshader', '--enable-webgl']});
try {
  const context = await browser.newContext();
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.abort();
    if (url.pathname.endsWith('/app-settings')) return route.fulfill({json:{ok:true,initialized:true,...settings}});
    if (/\/(app-view|app-views|app-control|desktop-view|app-revision|desktop-session)/.test(url.pathname)) return route.fulfill({json:{ok:true,commands:[],views:[]}});
    if (route.request().method() !== 'GET') return route.fulfill({json:{ok:true,discarded:true}});
    return route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', e=>console.error(e.message));
  await page.goto(origin+'/frozen/source.html?difficulty=easy', {waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.finalHarnessStandalone?.ready(),null,{timeout:120000});
  const info = await page.evaluate(()=>({clips:clips.map(c=>c.name),names,parents,
    sword: typeof swordMesh !== 'undefined' ? swordMesh : null}));
  console.log('SOURCE', JSON.stringify({clips:info.clips,joints:info.names.length,sword:!!info.sword}));
  const manifest = {schema:'attack_recovery_lab_v1',difficulty:'easy',seed:1234,
    sourceReceipt,names:info.names,parents:info.parents,clips:[]};
  await fs.mkdir(path.join(root,'data'),{recursive:true});
  if(info.sword) await fs.writeFile(path.join(root,'data/sword.json'),JSON.stringify(info.sword));
  for (const clipName of info.clips) {
    const sampled = await page.evaluate(name=>{
      finalHarnessStandalone.configureAuditCase({clipName:name,difficulty:'easy',startMirrored:false,frame:0});
      const sampled=finalHarnessStandalone.sampleDatasetCloudForActive('easy',20);
      return {sampled,fps:activeClip.fps,clipKeys:Object.keys(activeClip),
        armed:activeClip.armed_frame,hit:activeClip.hit_frame};
    },clipName);
    const clip={name:clipName,fps:sampled.fps,quotas:sampled.sampled.quotas,variants:[]};
    for(let i=0;i<20;i++) {
      const row=sampled.sampled.rows[i];
      const stem=`${clipName}_${String(i+1).padStart(2,'0')}`;
      const metaPath=path.join(root,'data',stem+'.json');
      let existing=null;
      try {existing=JSON.parse(await fs.readFile(metaPath));} catch(e) {if(e.code!=='ENOENT')throw e;}
      if(existing) {
        if(existing.sourceSha!==sourceReceipt.files['source.html'].sha256 || JSON.stringify(existing.target)!==JSON.stringify(row.targetWorldM))throw Error('Existing motion has a different source/target: '+stem);
        const bytes=await fs.readFile(path.join(root,existing.file));
        if(sha(bytes)!==existing.sha256) throw Error('Corrupt motion: '+stem);
        clip.variants.push(existing);continue;
      }
      const result=await page.evaluate(({name,target})=>{
        finalHarnessStandalone.configureAuditCase({clipName:name,difficulty:'easy',startMirrored:false,targetWorldM:target,frame:0});
        const capture=finalHarnessStandalone.visibleTrajectoryCapture();
        const points=Float32Array.from(capture.points), axes=Float32Array.from(capture.axes);
        return {frameCount:capture.frameCount,jointCount:capture.jointCount,
          points:standaloneFloat32Base64(points),axes:standaloneFloat32Base64(axes),
          state:finalHarnessStandalone.state(),
          phases: {armed:activeClip.armed_frame, hit:activeClip.hit_frame},
          idle:flattenAttackDatasetPoses([finalHarnessStandalone.visibleSolutionAt(0)])};
      },{name:clipName,target:row.targetWorldM});
      const points=Buffer.from(result.points,'base64'), axes=Buffer.from(result.axes,'base64');
      const bytes=Buffer.concat([points,axes]);
      const entry={id:i+1,kind:row.samplingKind,target:row.targetWorldM,file:`data/${stem}.bin`,
        frames:result.frameCount,joints:result.jointCount,fps:clip.fps,phases:result.phases,
        sha256:sha(bytes),sourceSha:sourceReceipt.files['source.html'].sha256};
      await fs.writeFile(path.join(root,entry.file),bytes);
      await fs.writeFile(metaPath,JSON.stringify(entry,null,2));
      clip.variants.push(entry);
      console.log(`${clipName} ${i+1}/20 ${entry.kind} ${entry.frames} frames`);
    }
    manifest.clips.push(clip);
    await fs.writeFile(path.join(root,'data/manifest.partial.json'),JSON.stringify(manifest,null,2));
  }
  await fs.writeFile(path.join(root,'data/manifest.json'),JSON.stringify(manifest,null,2));
  console.log('DONE',manifest.clips.length*20);
} finally {await browser.close();}
