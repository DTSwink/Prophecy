// VM audit of the real app's scheduling/trim handlers with fake DOM and deferred
// motion preparation. Run: node Labs/FootIKLab/verify-trim-ui.cjs
// No browser, server, inference or live-state changes. Rendering is stubbed.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const R=require('./recovery.js'),RealK=require('./footik.js'),HTTP=require('./network.js');
const checks=[],check=(name,passed,measured)=>checks.push({name,passed:!!passed,...(measured===undefined?{}:{measured})});
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
async function until(test){for(let i=0;i<100;i++){if(test())return;await new Promise(resolve=>setImmediate(resolve));}throw Error('VM did not reach expected preparation boundary');}
function harness(){
 const nodes=new Map(),listeners={},timers=new Map(),seedRequests=[],sessions=[],extensions=[],drawTimes=[],accepted=[];
 let active=0,maxActive=0,timerId=0,saved=null;
 const element=id=>{if(!nodes.has(id))nodes.set(id,{id,style:{},dataset:{},value:0,checked:false,hidden:id==='error',disabled:false,tagName:'INPUT',type:'number',innerHTML:'',textContent:'',setAttribute(){},setPointerCapture(){},getBoundingClientRect(){return{left:0,width:512};},contains(){return false;},click(){return this.onclick?.();}});return nodes.get(id);};
 const context=vm.createContext({console:{info(){},error(){},log(){}},performance,Date,JSON,Math,Map,Set,Promise,
  Recovery:R,FootIK:{...RealK,decode:data=>({source:'mock NN',duration:data.request.duration,direction:data.request.direction,directionMeta:{totalDuration:5,commandSpeed:2},marker:data.request.phase})},BodyflipSupport:{},
  document:{hidden:false,scripts:[],activeElement:null,getElementById:element,querySelectorAll:()=>[],addEventListener:(name,fn)=>listeners['document:'+name]=fn},
  window:{addEventListener:(name,fn)=>listeners['window:'+name]=fn},location:{reload(){throw Error('Unexpected navigation');}},
  requestAnimationFrame:()=>1,cancelAnimationFrame(){},setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id),
  WebGLMotionRenderer:class{},FootPlatforms:{undoShortcut:()=>false},FootSurface:{},
  FootHTTP:{json:async(url,options)=>{if(url==='/state')return saved;if(url==='/resume'){const request=JSON.parse(options.body);seedRequests.push(request);return{request,cache:'test-seed'};}throw Error('Unexpected URL '+url);}},
  FootSurfaceCoupling:{createPreparation(decoded,settings){const session={settings,decoded,through:0};sessions.push(session);session.extend=end=>{
   if(end<=session.through)return Promise.resolve(session.model);
   const wait=deferred(),entry={session,end,wait};extensions.push(entry);active++;maxActive=Math.max(maxActive,active);
   return wait.promise.then(()=>{active--;session.through=end;return session.model={generatedThrough:end,duration:5,speed:2,metrics:{},marker:settings.phase,terrain:{},sample(){return{};}};},error=>{active--;throw error;});
  };return session;}},
  FootHandoff:{prepare(){throw Error('Unexpected legacy preparation');}},
  __drawTimes:drawTimes,__accepted:accepted
 });
 const source=fs.readFileSync(path.join(__dirname,'app.js'),'utf8'),boot=source.lastIndexOf('(async()=>{const [rig,saved,health]');assert(boot>0,'Boot marker must be identifiable');
 vm.runInContext(source.slice(0,boot)+`
 drawAll=function(){__drawTimes.push(time);};
 backendVersion=9;settings=K.sanitize({terrain:'incline',phase:0,trimOut:1});time=.45;
 persistence={save(){},flush:async()=>{},accept:v=>__accepted.push(v)};
 sourcesUnchanged=async()=>true;bind();
 globalThis.testAPI={prepare,extendTrim,seek,setPlaying,
  configure:patch=>{settings=K.sanitize({...settings,...patch});},
  state:()=>({time,playing,busy,phase:settings.phase,trimOut:settings.trimOut,marker:model?.marker,through:model?.generatedThrough,pending:preparePending,reloading,task:!!prepareTask}),
  snapshot,settings:()=>K.sanitize(settings)};
 `,context,{filename:'app.js'});
 return{api:context.testAPI,element,seedRequests,sessions,extensions,timers,drawTimes,accepted,
  get maxActive(){return maxActive;},setSaved:value=>saved=value};
}
async function main(){
 const h=harness(),a=h.api;
 const first=a.prepare();await until(()=>h.extensions.length===1);
 a.configure({phase:.2});const second=a.prepare();a.configure({phase:.7,trimOut:1.2});const third=a.prepare();
 check('rapid edits share one serialized preparation task',first===second&&second===third&&h.maxActive===1);
 h.extensions[0].wait.resolve();await until(()=>h.extensions.length===2);
 check('superseded result is not published',a.state().marker===undefined);
 check('intermediate settings are coalesced',equal(h.seedRequests.map(r=>r.phase),[0,.7])&&h.extensions[1].end===1.2);
 h.extensions[1].wait.resolve();await third;
 check('only latest settings publish and queue becomes idle',a.state().marker===.7&&!a.state().busy&&!a.state().task&&h.maxActive===1);
 check('surface seed is bounded and retains nominal full duration metadata',h.seedRequests.every(r=>r.duration===.1&&r.seedOnly===true&&r.totalDuration===5));
 check('preparation preserves selected playback time',a.state().time===.45);
 const initialExtensions=h.extensions.length,initialSeeds=h.seedRequests.length;
 a.configure({trimOut:.9});a.extendTrim();await Promise.resolve();
 check('shrinking trim does not request generation or discard prefix',h.extensions.length===initialExtensions&&h.seedRequests.length===initialSeeds&&a.state().through===1.2);
 a.seek(4);check('seek is capped to generated endpoint',a.state().time===1.2);
 a.seek(.7);
 const event=t=>({pointerId:1,clientX:6+t/5*500,preventDefault(){}}),out=h.element('trimOut');
 out.onpointerdown(event(2));
 check('end bracket previews only available motion',a.state().trimOut===2&&a.state().time===1.2);
 out.onpointerup(event(2));await until(()=>h.extensions.length===3);
 check('end commit requests only extension on the same physics session',h.extensions[2].session===h.extensions[1].session&&h.extensions[2].end===2&&h.seedRequests.length===initialSeeds);
 check('bracket release restores playback before async extension',a.state().time===.7&&h.timers.size===0);
 h.extensions[2].wait.resolve();await until(()=>!a.state().busy);
 check('extension completion preserves restored playback',a.state().time===.7&&a.state().through===2);
 h.setSaved({settings:{...a.settings(),trimOut:2.8},camera:{},playback:{time:1.1,playing:false}});
 const refresh=h.element('refresh').onclick();await until(()=>h.extensions.length===4);
 check('refresh with larger view-only trim extends rather than skipping',h.extensions[3].end===2.8&&h.extensions[3].session===h.extensions[2].session);
 h.extensions[3].wait.resolve();await refresh;
 check('refresh retains saved playback after extending',a.state().time===1.1&&a.state().through===2.8&&!a.state().reloading);
 const requestsBefore=h.extensions.length;
 h.setSaved({settings:{...a.settings(),trimOut:2},camera:{},playback:{time:4,playing:false}});
 await h.element('refresh').onclick();
 check('view-only refresh with smaller trim performs no preparation',h.extensions.length===requestsBefore);
 check('view-only refresh cannot claim a frame beyond generated motion',a.state().time<=a.state().through,a.state());
 // An actual preparation that starts while playing remembers that intent.
 a.seek(.6);a.setPlaying(true);a.configure({trimOut:3.2});const resumed=a.prepare();await until(()=>h.extensions.length===5);
 check('preparation pauses playback while busy',!a.state().playing&&a.state().busy);
 h.extensions[4].wait.resolve();await resumed;
 check('preparation restores previous play intent and time',a.state().playing&&a.state().time===.6);
 a.setPlaying(false);
 // Check command readouts after the tiny seed expires, without synthesizing a
 // long source gait. Facing must continue to turn, rather than freeze at .1s.
 const short={duration:.1,fps:30,rootYawDegrees:[0,3,6,9],direction:'backward',directionMeta:{totalDuration:5,commandSpeed:2,facingDegrees:180},travel:[0,.066,.133,.2]};
 const heading=RealK.rootHeading(short,1,{rootYawSpeed:90,rootYawStart:0,rootYawStop:null},2);
 check('root heading continues commanded yaw beyond seed',R.length(R.sub(heading,[-1,0,0]))<1e-8,heading);
 check('root travel readout extends beyond seed',RealK.travelAt(short,1.5)===3);
 const savedPath=path.join(__dirname,'snapshots/overnight-state.json');
 if(fs.existsSync(savedPath)){
  const saved=JSON.parse(fs.readFileSync(savedPath,'utf8')),live=harness();
  live.api.configure(saved.settings);live.api.seek(saved.playback.time);
  const loading=live.api.prepare();await until(()=>live.extensions.length===1);
  check('saved wall trim is a real interval and preparation stops at its endpoint',saved.settings.trimIn===0&&saved.settings.trimOut>3&&live.extensions[0].end===saved.settings.trimOut,{trimIn:saved.settings.trimIn,trimOut:saved.settings.trimOut});
  check('saved wall load requests only seed rather than full five-second gait',live.seedRequests.length===1&&live.seedRequests[0].seedOnly===true&&live.seedRequests[0].duration===.1);
  live.extensions[0].wait.resolve();await loading;
  check('saved wall playback time survives bounded load',Math.abs(live.api.state().time-saved.playback.time)<1/120,live.api.state());
 }
 const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
 check('network deadline helper loads before app',html.indexOf('src="network.js"')>=0&&html.indexOf('src="network.js"')<html.indexOf('src="app.js"'));
 let aborted=false,error='';
 try{await HTTP.request('/resume',{},'json',20,async(url,options)=>{options.signal.addEventListener('abort',()=>aborted=true);return{ok:true,json:()=>new Promise(()=>{})};});}catch(e){error=e.message;}
 check('request deadline includes a stalled response body',aborted&&/did not respond/.test(error));
 const result={passed:checks.every(c=>c.passed),checks,scope:'Real app control flow in VM with deferred fake surface sessions; no browser, server, inference or saved-state writes.'};
 fs.writeFileSync(path.join(__dirname,'trim-ui-verification.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify({passed:result.passed,checks:checks.length,failures:checks.filter(c=>!c.passed)}));
 if(!result.passed)process.exitCode=1;
}
main().catch(error=>{console.error(error);process.exitCode=1;});
