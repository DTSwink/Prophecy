exec(open('Saved/Diagnostics/AnalyzePelvisWide.py').read().split("on=load('on')")[0])
d=json.loads((p/'PelvisIsolationFinal-capture.json').read_text());r={x['tick']:x for x in d['rows']};assert d['reason']=='Complete';print(d['reason'],len(r),max(r));report=summary(r,350,386);print(report)
t,v,w=series(r,368,386);print('yaw',[(int(a),round(float(b[2]),3)) for a,b in zip(t,w)])
(p/'PelvisIsolationFinal-summary.json').write_text(json.dumps(report,indent=2))
log=pathlib.Path('Saved/Logs/GameAnimationSample3.log').read_text(errors='replace')
import re
tests=re.findall(r'\[2026.09.25-15.(?:18|19).*Test Completed\. Result=\{(\w+)\} Name=\{([^}]+)\} Path=\{([^}]+)\}',log)
assert len(tests)==60,len(tests)
assert tests[:30]==tests[30:], 'Old/new test results differ'
print('Identical suite results old/new:',{res:sum(x[0]==res for x in tests[:30]) for res in ('Success','Fail')})
(p/'RecoveryIsolation-native-results.json').write_text(json.dumps({'old_and_new_equal':True,'each':tests[:30]},indent=2))
