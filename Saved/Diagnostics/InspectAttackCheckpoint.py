import torch,json,pathlib,hashlib
p=pathlib.Path('C:/Users/singerie/Documents/Cursor/stepper/training/runs/20260923_pin_x12_latest_fetch_005607/checkpoint_step123793_d467d60bd11e.pt')
c=torch.load(p,map_location='cpu',weights_only=False)
def describe(v):
 if isinstance(v,torch.Tensor):return {'shape':list(v.shape),'dtype':str(v.dtype)}
 if isinstance(v,dict):return {str(k):describe(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [describe(x) for x in v] if len(v)<50 else str(type(v))+' len='+str(len(v))
 if isinstance(v,(str,float,int,bool)) or v is None:return v
 return str(v)
r={k:describe(v) for k,v in c.items() if 'optim' not in k}
r['file_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
out=pathlib.Path('Saved/Diagnostics/AttackCheckpoint-123793-inspect.json');out.write_text(json.dumps(r,indent=2),encoding='utf-8')
print('keys',list(c),'sha256',r['file_sha256'])
for k,v in r.items():
 if k not in ['lower_model','upper_model','model','frozen_walk','model_state_dict','lower','upper']:print(k,str(v)[:6500])
