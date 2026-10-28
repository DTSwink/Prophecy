"""Small isolated save-route test. No NN inference or running lab changes."""
import json, tempfile, threading, urllib.request, urllib.error
from pathlib import Path
import server

with tempfile.TemporaryDirectory(prefix='footik-state-') as folder:
    server.STATE_FILE=Path(folder)/'state.json'
    server.STATE_FILE.write_text(json.dumps({'schema':'foot-ik-lab-v1','settings':{'slopeAngle':45,'phase':.21},'camera':{'yaw':1},'playback':{'time':2}}))
    http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
    url=f'http://127.0.0.1:{http.server_port}'
    def post(data):
        request=urllib.request.Request(url+'/state',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as result:return json.load(result)
    def read():
        with urllib.request.urlopen(url+'/state') as result:return json.load(result)
    try:
        post({'client':'current','sequence':3,'changes':{'settings':{'slopeAngle':90,'phase':.69}}})
        post({'client':'older-tab','sequence':1,'changes':{'camera':{'yaw':2}}})
        assert read()['settings']=={'slopeAngle':90,'phase':.69},'camera edit in old tab must retain newer terrain'
        assert read()['camera']['yaw']==2
        assert post({'client':'current','sequence':1,'changes':{'settings':{'slopeAngle':45}}})['superseded']
        assert read()['settings']['slopeAngle']==90,'delayed old save cannot restore old slope'
        before=server.STATE_FILE.read_bytes()
        for invalid in [{'settings':{'slopeAngle':45}}, {'client':'bad','sequence':1,'changes':{'unknown':{}}}]:
            try:post(invalid);raise AssertionError('invalid save accepted')
            except urllib.error.HTTPError as error:assert error.code==400
            assert server.STATE_FILE.read_bytes()==before
        server.STATE_CLIENTS.clear() # A restart reads the durable file, not an in-memory scene.
        assert read()['settings']['slopeAngle']==90
        assert json.loads(server.STATE_FILE.read_text())==read()
        print('Server persistence: stale-tab, delayed-save, invalid-save and durable-state checks passed.')
    finally:
        http.shutdown();http.server_close();worker.join()
