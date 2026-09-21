from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[2]
def read(p):
    rows={};key=None
    raw=p.read_bytes()
    for line in raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig').splitlines():
        if ' | ' in line:
            cols=line.split(' | ');key=tuple(cols[:3])
        elif line.startswith('  ') and '= ' not in line[:3] and ' ->' in line:
            left,links=line.strip().split(' ->',1)
            pin,default=left.split('=',1)
            rows[(*key,pin)]=(default,set(links.split()))
    return rows
before=read(root/'Saved/Diagnostics/FineGrainedBlends-Before.txt')
after=read(root/'Saved/Diagnostics/SwordThigh/BlueprintGraph.txt')
errors=[];normalized=0;empty_key_outputs=0
for key,(value,links) in before.items():
    if key not in after: errors.append(f'Missing pin {key}');continue
    newvalue,newlinks=after[key]
    if value!=newvalue:
        cdo=re.fullmatch(r' /Engine/Transient\.BPGC_ARCH_FOR_CDO_(\w+)_\d+',value)
        if key[-1]=='self' and cdo and newvalue==' /Script/GameAnimationSample3.Default__'+cdo[1]: normalized+=1
        elif key[-2].startswith('K2Node_InputKey_') and key[-1]=='Key' and value=='None None' and newvalue==' None' and not links and not newlinks:
            empty_key_outputs+=1 # Compiler normalizes unused output defaults, not key bindings.
        else: errors.append(f'Changed default {key}: {value} -> {newvalue}')
    if not links<=newlinks: errors.append(f'Removed link {key}: {links-newlinks}')
    for dest in newlinks-links:
        node,pin=dest.rsplit('.',1)
        if (*key[:2],node,pin) in before: errors.append(f'New link to old pin {key}: {dest}')
result={'old_pins':len(before),'new_pins':len(set(after)-set(before)),'restored_native_cdo_references':normalized,'normalized_unused_key_outputs':empty_key_outputs,'preserved':not errors,'errors':errors}
(root/'Saved/Diagnostics/FineGrainedBlends-Wiring.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
assert not errors
