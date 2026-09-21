import json,pathlib,re
root=pathlib.Path(__file__).resolve().parent
log=(root/'EditorRecovered-FixedClock.log').read_text(encoding='utf-8',errors='replace')
start=list(re.finditer(r'Found (\d+) automation tests based on',log))[-1]
section=log[start.start():]
tests=re.findall(r'Test Completed\. Result=\{([^}]+)\} Name=\{[^}]+\} Path=\{([^}]+)\}',section)
result={'expected':int(start[1]),'count':len(tests),'failed':[name for status,name in tests if status!='Success'],
        'tests':[{'name':name,'status':status} for status,name in tests]}
(root/'fixed-clock-regressions.json').write_text(json.dumps(result,indent=2))
(root/'FixedClockRegressions.log').write_text(section,encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='tests'}))
assert result['count']==result['expected']==91
assert not result['failed']
