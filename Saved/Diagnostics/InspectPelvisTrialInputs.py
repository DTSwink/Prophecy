import pathlib,json,numpy as np
p=pathlib.Path('Saved/Diagnostics')
def load(name):return {round(x['time']*60):x for x in map(json.loads,(p/(name+'-nn.jsonl')).read_text().splitlines()) if x['actor'].endswith('_C_1')}
a=load('PelvisWide-off320');b=load('PelvisDisplayTrial-paired')
for t in range(323,341,2):
 x=np.array(a[t]['lower_input']);y=np.array(b[t]['lower_input']);d=abs(x-y);ix=np.argsort(d)[-8:][::-1];print(t,'pose',max(d[:41]),'big',[(int(i),round(float(d[i]),5)) for i in ix]);print('feet',np.round(d[[9,10,11,25,26,27]],5),'thigh',round(max(d[18:24]),5),round(max(d[34:40]),5))
