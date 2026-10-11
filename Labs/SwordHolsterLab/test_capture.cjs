// Read-only browser: verifies worker images against the actual framebuffer,
// including pose/camera changes while encoding and reduced live previews.
const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl']});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1050},deviceScaleFactor:1.25}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8818/');await page.waitForFunction(()=>holsterLab.ready);
  for(const variant of [0,1,2]){
   if(variant===2)await page.setViewportSize({width:1100,height:800});
   const report=await page.evaluate(async variant=>{
    holsterLab.setPlaying(false);
    $('upperOnly').checked=variant!==1;$('idleGhost').checked=variant===1;$('skeleton').checked=variant===1;$('handGizmos').checked=variant===2;
    holsterLab.seek((variant+1)*.73);
    const pose=JSON.stringify(currentPose),width=$('viewport').width,height=$('viewport').height;
    const reference=new Promise(r=>$('viewport').toBlob(r,'image/png'));
    const captured=canvasPNG();
    // Pending capture must retain its submitted image, despite later frames.
    holsterLab.seek((variant+1)*.91);cameraState.yaw+=.2;drawAll();
    const blob=await(await fetch(await captured)).blob();
    const [a,b]=await Promise.all([createImageBitmap(await reference),createImageBitmap(blob)]);
    const pixels=image=>{const c=new OffscreenCanvas(image.width,image.height),ctx=c.getContext('2d');ctx.drawImage(image,0,0);return ctx.getImageData(0,0,c.width,c.height).data;};
    const pa=pixels(a),pb=pixels(b);let max=0,different=0;
    for(let i=0;i<pa.length;i++){const d=Math.abs(pa[i]-pb[i]);max=Math.max(max,d);if(d>1)different++;}
    const first=canvasPNG({preview:true}),second=canvasPNG({preview:true});
    const preview=await createImageBitmap(await(await fetch(await first)).blob());
    return {width,height,captured:[b.width,b.height],preview:[preview.width,preview.height],max,different,cached:first===second,changed:JSON.stringify(currentPose)!==pose,errors:holsterLab.errors};
   },variant);
   assert.deepEqual(report.captured,[report.width,report.height]);assert(report.changed);assert(report.cached);assert(Math.max(...report.preview)<=640);
   assert(report.max<=1&&report.different===0,JSON.stringify(report));assert.deepEqual(report.errors,[]);console.log({variant,...report});
  }
  assert.deepEqual(errors,[]);console.log('PASS: worker captures match framebuffer, preserve submitted pose/camera, resize, ghost/gizmos and full-resolution snapshots.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
