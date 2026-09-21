import json
print('frames',kick_knee_capture.n,'events',kick_knee_capture.events[-8:])
print('recent',[(r['agent'],r['attack'],r['mode'],list(r['meshes'])) for r in kick_knee_capture.rows[-5:]])
(kick_knee_capture.out/'interim.json').write_text(json.dumps({'rows':kick_knee_capture.rows,'events':kick_knee_capture.events},default=str))
print('attack samples',sum(bool(r['attack']) for r in kick_knee_capture.rows))
