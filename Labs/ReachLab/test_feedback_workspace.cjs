// App integration in an owned headless browser/service; never the live desktop.
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),net=require('net'),assert=require('assert/strict'),{spawn}=require('child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachGripFeedback20261016'),store=fs.mkdtempSync(path.join(out,'workspace-')),probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe'});let browser;
 try{
  const url=`http://127.0.0.1:${port}`;for(let i=0;;i++){try{if((await fetch(url+'/health')).ok)break;}catch(e){if(i>100)throw e;}await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});const page=await browser.newPage({viewport:{width:1100,height:780}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(url+'/reach');await page.waitForFunction(()=>window.reachLab?.restore);await page.evaluate(async()=>{setPlaying(false);await settled();});
  const results=[];
  for(const name of ['UE_Grip_Feedback_Before','UE_Grip_Feedback']){
   const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'snapshots',name+'.json'),'utf8'));
   const result=await page.evaluate(async s=>{
    await reachLab.restore(s,{save:false});for(let i=0;i<30;i++)await step(1,false);const saved=snapshot();for(let i=0;i<20;i++)await step(1,false);const end=snapshot();await reachLab.restore(saved,{save:false});for(let i=0;i<20;i++)await step(1,false);const replay=snapshot();
    const deterministic=['pose','solverState','grabs'].every(k=>JSON.stringify(end[k])===JSON.stringify(replay[k]));
    await restartCapturedScenario();const restarted=snapshot();
    const resetTargetError=Math.max(...settings.hands.map((h,k)=>norm(sub(h.target,s.settings.hands[k].target))));
    settings.hands[1].target=add(settings.hands[1].target,[0,0,5]);await step(1,false);await restartCapturedScenario();const dragPreserved=norm(sub(settings.hands[1].target,add(s.settings.hands[1].target,[0,0,5])))<1e-8;
    await reachLab.restore(s,{save:false});drawAll();return {deterministic,resetTargetError,dragPreserved,restartedTick:restarted.tick,feedbackRetained:restarted.grabs.every(g=>!!g.feedback),image:await capturePNG(copy(renderData()))};
   },fixture);
   fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(result.image.split(',')[1],'base64'));delete result.image;assert(result.deterministic&&result.resetTargetError<1e-8&&result.dragPreserved&&result.feedbackRetained);results.push({name,...result});
  }
  // Standard lab acquisition still uses the original thresholds and finger fit.
  const standard=await page.evaluate(async()=>{settings=defaults();resetPose();for(let i=0;i<240;i++)await step(1,false);return grabs.map(g=>({held:g.gripped,angle:g.angle,distance:g.distance,contacts:g.contacts,fitCount:g.fitCount}));});assert(standard.every(g=>g.held&&g.contacts>=3&&g.fitCount===1));assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'workspace-verification.json'),JSON.stringify({passed:true,results,standard,errors},null,2));console.log(JSON.stringify({passed:true,results,standard},null,2));
 }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
