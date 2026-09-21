import json,pathlib,re
root=pathlib.Path(__file__).resolve().parent
project=root.parents[2]
log=(project/'Saved/JoltMigration/RuntimeSelfCollision-20260910/Editor.log').read_text(encoding='utf-8',errors='replace')
start=list(re.finditer(r'Found (\d+) automation tests based on',log))[-1]
text=log[start.start():]
tests=re.findall(r'Test Completed\. Result=\{([^}]+)\} Name=\{[^}]+\} Path=\{([^}]+)\}',text)
assert len(tests)==int(start[1])==86,(len(tests),start[1])
result={'count':len(tests),'failed':[name for status,name in tests if status!='Success'],
        'tests':[{'name':name,'status':status} for status,name in tests]}
(root/'regressions.json').write_text(json.dumps(result,indent=2))
(root/'Regressions.log').write_text(text,encoding='utf-8')
print(json.dumps({'count':result['count'],'failed':result['failed']}))
assert not result['failed']
