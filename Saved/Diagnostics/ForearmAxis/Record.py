from pathlib import Path
import re,json
p=Path(__file__).resolve().parent
text=(p/'Automation.log').read_text(errors='replace')
start=text.rfind('Found 7 automation tests')
assert start>=0
text=text[start:]
tests=[dict(result=result,path=path) for result,path in re.findall(r'Test Completed\. Result=\{(.*?)\} Name=\{.*?\} Path=\{(.*?)\}',text)]
errors=[s for s in text.splitlines() if 'Error:' in s]
warnings=[s for s in text.splitlines() if 'LogAutomationController: Warning:' in s]
result={'build_succeeded':'Result: Succeeded' in (p/'Build.log').read_text(),'tests':tests,'errors':errors,'warnings':warnings}
(p/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
assert result['build_succeeded'] and len(tests)==7 and not errors and all(t['result']=='Success' for t in tests)

