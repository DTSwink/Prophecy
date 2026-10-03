import json,pathlib,numpy as np
p=pathlib.Path('Saved/SlashTrain2223')
a=json.loads((p/'chain_audit.json').read_text())
b=np.load(r'C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260922_latest_chained_variants/latest_predictive_pin_x5_20260924_refresh2/seed_2026092223/complete/rollout.npz')
x=np.array(a['expected'])[:,131:206].reshape(-1,25,3)
print('oracle versus recorded viewer cm',np.max(np.linalg.norm(x-b['positions'][2:],axis=-1))*100,x.shape)
g=json.loads((p/'source_native_geometry.json').read_text());print('source carrier',g['root_position'],g['root_rotation'])
f=json.loads(pathlib.Path('Tools/NN/Fixtures/SlashTrain2026092223.json').read_text()); print('root-local first pelvis',f['initial_history']['positions'][1][0],a['inputs'][0][41:44])
