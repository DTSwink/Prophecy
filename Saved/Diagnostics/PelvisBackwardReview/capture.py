import pathlib
import time
import unreal

root = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics'
scope = {'__name__': '__pelvis_review__'}
exec(compile((root / 'PelvisBackward/capture_live.py').read_text(encoding='utf-8'), 'capture_live.py', 'exec'), scope)
state = scope['state']
output = root / 'PelvisBackwardReview'
output.mkdir(parents=True, exist_ok=True)
state['duration'] = 90.0
state['path'] = str(output / ('capture-' + time.strftime('%H%M%S') + '.json'))
print('REVIEW_CAPTURE', state['path'], 'No test settings or hitches applied')
