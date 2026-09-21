import json, pathlib, re, sys
root=pathlib.Path(__file__).resolve().parent
project=root.parents[2]
log=(project/'Saved/JoltMigration/RuntimeSelfCollision-20260910/Editor.log').read_text(encoding='utf-8',errors='replace')
starts=list(re.finditer(r'Found (\d+) automation tests based on',log))
start=starts[-1]
text=log[start.start():]
tests=re.findall(r'Test Completed\. Result=\{([^}]+)\} Name=\{[^}]+\} Path=\{([^}]+)\}',text)
assert len(tests)==int(start[1])==84,(len(tests),start[1])
result={'count':len(tests),'failed':[name for status,name in tests if status!='Success'],
        'tests':[{'name':name,'status':status} for status,name in tests],
        'warnings':[line for line in text.splitlines() if 'LogAutomationController: Warning:' in line]}
prefix=sys.argv[1] if len(sys.argv)>1 else ''
(root/(prefix+'regressions.json')).write_text(json.dumps(result,indent=2))
(root/(prefix+'Regressions.log')).write_text(text,encoding='utf-8')
print(json.dumps({'count':result['count'],'failed':result['failed'],'warnings':len(result['warnings'])}))
assert not result['failed']
