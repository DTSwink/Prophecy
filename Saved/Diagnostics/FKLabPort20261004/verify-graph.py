from pathlib import Path
import re,json,difflib
p=Path(__file__).parent

def read(name):
 raw=(p/name).read_bytes();return raw.decode('utf-16') if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else raw.decode('utf-8-sig')
def norm(text):
 text=re.sub(r'/Script/\w+\.Default__(\w+)',r'CDO_\1',text)
 text=re.sub(r'/Engine/Transient\.BPGC_ARCH_FOR_CDO_(\w+)_\d+',r'CDO_\1',text)
 # Cold reload canonicalizes numeric default strings and empty Key output pins.
 text=re.sub(r'(?<![\w.])0(?:\.0+)?(?![\w.])','0',text)
 text=text.replace('0, 0, 0','0,0,0').replace('  Key=None None ->','  Key= None ->')
 return text
before,after=norm(read('before-graph.txt')),norm(read('after-graph.txt'))
def blocks(text):return {s.splitlines()[0]:s for s in text.split('\n\n') if s.strip()}
a,b=blocks(before),blocks(after)
assert set(a)==set(b),'Node inventory changed'
changes=[name for name in a if sorted(a[name].splitlines())!=sorted(b[name].splitlines())]
assert all(any(n in k for n in ['K2Node_CallFunction_224 |','K2Node_CallFunction_206 |','K2Node_MacroInstance_1 |']) for k in changes),changes
main=next(v for k,v in b.items() if 'K2Node_CallFunction_43 | Set Attack FK Return' in k)
assert 'AlphaHold=1.000000' in main and 'Trim=0 None' in main
old=next(v for k,v in b.items() if 'K2Node_CallFunction_224 |' in k)
assert '  execute= None ->\n' in old+'\n',old
(p/'graph-diff.txt').write_text('\n'.join(difflib.unified_diff(before.splitlines(),after.splitlines())),encoding='utf-8')
(p/'graph-verification.json').write_text(json.dumps({'nodes':len(a),'changed':changes,'hold':1,'trim':0,'verified':True},indent=2))
print('Verified only two profile-node pin updates and old override disconnection; Hold1/Trim0 preserved.')
