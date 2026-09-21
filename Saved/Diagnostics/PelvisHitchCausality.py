import json,pathlib,numpy as np
root=pathlib.Path(__file__).parent
def load(name):
    path=root/name
    ps=[json.loads(x) for x in (path/'pipeline.jsonl').read_text().splitlines()]
    return {round(r['time']*60):r for r in ps if r['actor'].endswith('_C_1')}
b=load('PelvisHitch-20260920-193832');a=load('PelvisHitch-20260920-194230')
result={}
for tick in (171,173,175,177,179,181):
    x=b[tick];y=a[tick]
    d=lambda key,lo,hi:float(np.max(np.abs(np.array(x[key][lo:hi])-y[key][lo:hi])))
    result[tick]={'input_pelvis_max':d('lower_input',0,9),'input_legs_max':d('lower_input',9,41),'input_previous_pelvis_max':d('lower_input',41,50),
        'input_previous_legs_max':d('lower_input',50,82),'root_input_max':d('lower_input',117,len(x['lower_input'])),
        'pelvis_prediction_delta_max':d('lower_delta',0,3),'pelvis_published_max':d('published_lower',0,9),'legs_published_max':d('published_lower',9,41),
        'tempering_base':x.get('tempering'),'tempering_ablation':y.get('tempering')}
print(json.dumps(result,indent=2))
for tick in (173,175):
    x=b[tick];y=a[tick]
    print('Detailed',tick)
    for label,lo,hi in [('pelvis position',0,3),('left foot position',9,12),('left foot rotation',12,18),('left thigh rotation',18,24),('right foot position',25,28),('right foot rotation',28,34),('right thigh rotation',34,40)]:
        print(label, np.round(np.array(x['published_lower'][lo:hi])-y['published_lower'][lo:hi],6).tolist())
(root/'PelvisHitch-20260920-193832'/'causality.json').write_text(json.dumps(result,indent=2))
