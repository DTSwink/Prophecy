"""Verify compact live saves and planned motion on an owned isolated service."""
from pathlib import Path
import subprocess,sys,socket,tempfile,json,time,uuid,urllib.request,os,shutil,statistics

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]/'Saved/Diagnostics/ReachPlan20261016'
store=Path(tempfile.mkdtemp(prefix='isolated-',dir=OUT));(store/'snapshots').mkdir()
for file in (HERE/'snapshots').glob('TestNN*.json'):shutil.copy2(file,store/'snapshots'/file.name)
with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
url=f'http://127.0.0.1:{port}';token=uuid.uuid4().hex
headers={'Content-Type':'application/json','X-Desktop-Session':token,'X-Client-Id':'storage-test'}
def request(path,data=None):
 req=urllib.request.Request(url+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
 with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
child=subprocess.Popen([sys.executable,str(HERE/'server.py'),'--port',str(port),'--state-dir',str(store)],creationflags=subprocess.CREATE_NO_WINDOW)
try:
 for _ in range(60):
  try:request('/health');break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('Isolated REACH server did not start')
 request('/desktop-session',{'token':token})
 s=json.loads((HERE/'snapshots/TestNN_Right_Recorded.json').read_text())
 identifier=request('/motion',s['motion'])['id'];compact={**s};motion=compact.pop('motion');compact['motionRef']={'id':identifier,'startTick':motion['startTick']}
 request('/session',compact);assert request('/session')==s
 assert request('/motions/'+identifier+'.json')==motion
 import base64
 png=base64.b64encode((HERE/'snapshots/TestNN_Right_Recorded.png').read_bytes()).decode()
 packet={**compact,'state':compact,'sequence':1,'image':'data:image/png;base64,'+png}
 times=[]
 for sequence in range(1,6):
  packet['sequence']=sequence;t=time.perf_counter();request('/desktop-view',packet);times.append((time.perf_counter()-t)*1000)
 live=request('/desktop-view');assert 'motion' not in live and 'motion' not in live['state']
 assert request('/session')==s
 # Older open windows must remain compatible until the user's Refresh.
 request('/desktop-view',{**s,'state':s,'sequence':6,'image':packet['image']})
 assert request('/desktop-view')['state']['motionRef']==compact['motionRef']
 assert request('/session')==s
 receipt={'passed':True,'compactLiveSaveRoundtripMs':times,'liveBytes':(store/'current_view.json').stat().st_size,'sessionBytes':(store/'session.json').stat().st_size,'motionFiles':len(list((store/'motions').glob('*.json'))),'fullRestoreExact':True,'oldClientCompatible':True}
 (OUT/'storage-verification.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
 env={**os.environ,'REACH_TEST_URL':url}
 node=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
 subprocess.run([str(node),str(HERE/'test_plan.cjs')],env=env,check=True)
finally:
 child.terminate();child.wait(timeout=10)
