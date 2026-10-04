from pathlib import Path
import re,json,difflib
p=Path(__file__).parent
names=['Headbutt','HookL','HookR','JabL','JabR','KickL','KickR','OverL','OverR','Pike','SlashL','SlashLD','SlashLU','SlashR','SlashRD','SlashRU']
def read(n):
 b=(p/n).read_bytes();return b.decode('utf-16') if b[:2] in (b'\xff\xfe',b'\xfe\xff') else b.decode('utf-8-sig')
def norm(t):
 t=re.sub(r'/Script/\w+\.Default__(\w+)',r'CDO_\1',t)
 t=re.sub(r'/Engine/Transient\.BPGC_ARCH_FOR_CDO_(\w+)_\d+',r'CDO_\1',t)
 t=re.sub(r'(?<![\w.])0(?:\.0+)?(?![\w.])','0',t)
 return t.replace('0, 0, 0','0,0,0').replace('  Key=None None ->','  Key= None ->')
def blocks(t):return {x.splitlines()[0]:sorted(x.splitlines()[1:]) for x in t.split('\n\n') if x.strip()}
a,b=blocks(norm(read('before-graph.txt'))),blocks(norm(read('after-graph.txt')))
assert a.keys()==b.keys(),'Node inventory changed'
changed=[k for k in a if a[k]!=b[k]]
assert len(changed)==2 and all(k.endswith(' | Set Attack FK Return') for k in changed),changed
for k in changed:
 before=[s for s in a[k] if not s.startswith(('  AlphaHold=','  Trim='))]
 after=[s for s in b[k] if not any(s.startswith('  '+n+'=') for n in names)]
 assert before==after,(k,before,after)
 for name in names:
  pin=next(s for s in b[k] if s.startswith('  '+name+'='))
  nums=re.findall(r'[-+]?\d*\.\d+|\d+',pin.split(' None ->')[0].split('=',1)[1]);assert [float(v) for v in nums]==[.1,.34],pin
(p/'graph-verification.json').write_text(json.dumps({'verified':True,'nodes':len(a),'changed':changed,'defaults':[.1,.34]},indent=2))
print('Only two Set Attack FK Return nodes changed; all 16 vectors default .1/.34, other pins/wiring preserved.')
