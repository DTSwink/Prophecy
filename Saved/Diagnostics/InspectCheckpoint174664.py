import torch,json
from pathlib import Path
old=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260923_pin_x12_latest_fetch_005607/checkpoint_step123793_d467d60bd11e.pt')
new=Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260922_latest_chained_variants/best_total_172k175k_20260924/checkpoint_step174664_3c68cbeec601.pt')
a=torch.load(old,map_location='cpu',weights_only=False);b=torch.load(new,map_location='cpu',weights_only=False)
print('RECIPE_DIFF',json.dumps({k:[a['recipe'].get(k),b['recipe'].get(k)] for k in a['recipe'].keys()|b['recipe'].keys() if a['recipe'].get(k)!=b['recipe'].get(k)},default=str))
print('PIN', {k:v for k,v in b.get('pin_strength',{}).items() if k!='program'})
print('EXTRA_KEYS',b.keys()-a.keys())
