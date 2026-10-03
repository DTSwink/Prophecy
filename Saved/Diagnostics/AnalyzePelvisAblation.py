exec(open('Saved/Diagnostics/AnalyzePelvisWide.py').read().split("on=load('on')")[0])
for mode in ('pole','source','length','support'):
 file=p/f'PelvisAblation-{mode}-capture.json'
 if not file.exists():continue
 data=json.loads(file.read_text());r={x['tick']:x for x in data['rows']};print(mode,data['reason']);print(summary(r,350,386))
 t,v,w=series(r,368,386);print([(int(a),round(float(b[2]),2)) for a,b in zip(t,w)])
