const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
(async()=>{
 const root=__dirname,out=path.resolve(root,'../../Saved/Diagnostics/ElbowDraw20261014/normal-motion-ui');fs.mkdirSync(out,{recursive:true});
 const original=JSON.parse(fs.readFileSync(path.join(root,'state.json'))),store=fs.mkdtempSync(path.join(out,'state-'));
 const seed=original.problemEnabled?original.normalMotionState:original;fs.writeFileSync(path.join(store,'state.json'),JSON.stringify({...seed,problemEnabled:false,problemStates:{},normalMotionState:null}));
 const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(root,'backend.py'),'--port','8829','--state-dir',store],{windowsHide:true,stdio:'ignore'});let browser;
 try{
  for(let i=0;i<80;i++){try{if((await fetch('http://127.0.0.1:8829/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  assert.equal(path.resolve((await(await fetch('http://127.0.0.1:8829/health')).json()).store),path.resolve(store));
  const token='test-'+require('node:crypto').randomUUID();await fetch('http://127.0.0.1:8829/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8829/?desktopSession='+token);await page.waitForFunction(()=>window.holsterLab?.ready);
  if(await page.locator('#problemEnabled').isChecked())await page.uncheck('#problemEnabled');
  await page.evaluate(()=>holsterLab.seek(.6));
  const normal=await page.evaluate(()=>holsterLab.state());
  await page.check('#problemEnabled');assert.equal(await page.locator('#motion option').count(),6);
  for(let c=0;c<3;c++){
   await page.selectOption('#motion','problem_'+c);
   const summary=await page.evaluate(()=>{const m=holsterLab.model();return {duration:m.playbackDuration,phases:[...new Set(m.frames.map(f=>f.phase))],complete:m.completionTick};});
   for(const phase of ['Reach','Slide','FK return','Held'])assert(summary.phases.includes(phase));assert(summary.complete>0);assert(summary.duration>1);
   await page.click('#start');await page.click('#play');await page.waitForTimeout(250);
   const t1=await page.evaluate(()=>holsterLab.pose().diagnostics.playbackTime);await page.waitForTimeout(250);
   const t2=await page.evaluate(()=>holsterLab.pose().diagnostics.playbackTime);assert(t2>t1+.03,'Playback must actually advance, not just change the button');
   await page.keyboard.press('Space');assert.equal(await page.locator('#play').textContent(),'Play');
   if(!await page.locator('#fkReturnPanel').isVisible())await page.click('#openFKReturn');assert(await page.locator('#fkReturnPanel').isVisible());await page.click('#closeFKReturn');
   await page.click('#openBodyTargets');assert(await page.locator('#bodyTargetsPanel').isVisible());await page.click('#closeBodyTargets');
  }
  await page.selectOption('#motion','problem_0');await page.click('#openFKReturn');
  const sample=()=>page.evaluate(()=>{const m=holsterLab.model(),r=m.armReturn||m.fkReturn;holsterLab.seek(r.start+3/60);return holsterLab.pose().points;});
  assert.equal(await page.locator('#fk_elbowSoftZone, #fk_elbowIKCorrection').count(),2,'IK correction controls restored');
  await page.locator('#fkReturnPanel summary').filter({hasText:'Inertia options'}).click();
  await page.check('#fk_elbowIKCorrection');const corrected=await sample();
  await page.uncheck('#fk_elbowIKCorrection');const uncorrected=await sample();
  assert.notDeepEqual(corrected,uncorrected,'checkbox must change generated return');
  await page.check('#fk_elbowIKCorrection');assert.deepEqual(await sample(),corrected,'restoring correction is deterministic');
  await page.selectOption('#motion','problem_0');
  const before=await sample();await page.locator('#fk_inertia').evaluate(el=>{el.value='0';el.dispatchEvent(new Event('change',{bubbles:true}));});const after=await sample();
  assert(Math.max(...before.flat().map((v,i)=>Math.abs(v-after.flat()[i])))>.001,'FK controls must affect generated motion');
  await page.selectOption('#motion','problem_1');assert.notEqual(await page.locator('#fk_inertia').inputValue(),'0');
  await page.selectOption('#motion','problem_0');assert.equal(await page.locator('#fk_inertia').inputValue(),'0');
  await page.waitForTimeout(450);await page.reload();await page.waitForFunction(()=>holsterLab?.ready);
  assert(await page.locator('#problemEnabled').isChecked());assert.equal(await page.locator('#motion').inputValue(),'problem_0');assert.equal(await page.locator('#fk_inertia').inputValue(),'0');
  await page.click('#closeFKReturn');await page.click('#openBodyTargets');

  // Exercise the existing worker through a body-plan slider while using captured input.
  await page.locator('#pelvisRotationCompensation').evaluate(el=>{el.value='.5';el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));});
  await page.waitForFunction(()=>holsterLab.model().o.pelvisRotationCompensation===.5);
  assert.equal(await page.evaluate(()=>holsterLab.model().o.motion),'problem_0');
  await page.click('#closeBodyTargets');await page.evaluate(()=>{const m=holsterLab.model();holsterLab.seek((m.armReturn||m.fkReturn).start+.05);});
  await page.screenshot({path:path.join(out,'problem-checkbox.png')});
  await page.uncheck('#problemEnabled');const restored=await page.evaluate(()=>holsterLab.state());
  assert.deepEqual(restored.parameters,normal.parameters);assert.deepEqual(restored.camera,normal.camera);assert.equal(restored.time,normal.time);assert.equal(restored.controls.speed,normal.controls.speed);
  await page.check('#problemEnabled');
  for(const [id,tick] of [['problem_3',660],['problem_4',1138],['problem_5',181]]){
   await page.selectOption('#motion',id);
   await page.waitForTimeout(450);await page.reload();
   await page.waitForFunction(()=>holsterLab?.ready,{},{timeout:5000}).catch(async e=>{throw Error((await page.locator('#error').textContent())+'; '+e.message);});
   await page.evaluate(tick=>holsterLab.seek((tick-holsterLab.model().returnCapture.firstTick)/60),tick);
   assert((await page.locator('#time').textContent()).includes('UE tick '+tick));
   await page.screenshot({path:path.join(out,id+'-captured.png')});
   if(!await page.locator('#fkReturnPanel').isVisible())await page.click('#openFKReturn');
   assert.equal(await page.locator('#fk_elbowSoftZone, #fk_elbowIKCorrection').count(),2);
   const editInertia=async value=>page.locator('#fk_inertia').evaluate((el,v)=>{el.value=String(v);el.dispatchEvent(new Event('change',{bubbles:true}));},value);
   const inertiaPose=()=>page.evaluate(()=>{const m=holsterLab.model();holsterLab.seek((m.returnCapture.release+1)/60);return {points:holsterLab.pose().points.flat(),duration:m.armReturn.timing.duration};});
   const originalInertia=await page.locator('#fk_inertia').inputValue();
   await editInertia(0);const zeroPose=await inertiaPose();await editInertia(.001);const tinyPose=await inertiaPose();
   assert.equal(zeroPose.duration,tinyPose.duration,'inertia must not alter return duration');
   assert(Math.max(...zeroPose.points.map((v,i)=>Math.abs(v-tinyPose.points[i])))<.1,'tiny inertia must not produce the old elbow jump');
   await editInertia(originalInertia);
   const editArc=async value=>page.locator('#fk_swordPointSpeed').evaluate((el,v)=>{el.value=String(v);el.dispatchEvent(new Event('change',{bubbles:true}));},value);
   const arcPose=()=>page.evaluate(()=>{const m=holsterLab.model(),i=m.returnCapture.release+5;holsterLab.seek(i/60);return m.frames[i].pose[m.arm[2]].q;});
   await editArc(180);const positive=await arcPose();await editArc(-180);const negative=await arcPose();
   assert(Math.max(...positive.map((v,i)=>Math.abs(v-negative[i])))>.01,'captured sword angular speed control must change the actual hand rotation');
   await editArc(0);assert.equal(await page.evaluate(()=>!!holsterLab.model().swordPoint),false);
   await editArc(180);await page.waitForTimeout(450);await page.reload();await page.waitForFunction(()=>holsterLab?.ready);
   assert.equal(await page.locator('#fk_swordPointSpeed').inputValue(),'180');assert.deepEqual(await arcPose(),positive,'arc survives reload');
   await page.click('#closeFKReturn');await page.click('#start');await page.click('#play');await page.waitForTimeout(180);
   assert(await page.evaluate(()=>holsterLab.pose().diagnostics.playbackTime)>.05);await page.keyboard.press('Space');
  }
  await page.uncheck('#problemEnabled');
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);
  console.log('PASS: six problem motions, restored IK checkbox, real playback, both panels, independent tuning/reload, worker replanning and normal restore.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
