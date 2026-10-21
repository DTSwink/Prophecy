"""Verify the installer only adds its own graph and retains authored graphs verbatim."""
import pathlib,re,sys,json,hashlib
root=pathlib.Path(__file__).resolve().parents[2]
folder=root/'Saved/Diagnostics/SwordBloodDepth'
def graphs(name):
    text=(folder/name).read_text(encoding='utf-8-sig')
    result={}
    authored=set(re.findall(r"^   (?:FunctionGraphs|UbergraphPages|MacroGraphs|DelegateSignatureGraphs)\(\d+\)=\"/Script/Engine.EdGraph'([^']+)'",text,re.M))
    lines=text.splitlines()
    for i,line in enumerate(lines):
        match=re.match(r'   Begin Object Name="([^"]+)" ExportPath="/Script/Engine.EdGraph',line)
        if match and match[1] in authored:
            end=next(j for j in range(i+1,len(lines)) if lines[j]=='   End Object')
            result[match[1]]='\n'.join(lines[i:end+1])
    return result
additive='--additive' in sys.argv
seeded='--seed' in sys.argv
before,after=graphs('before-seed.txt' if seeded else 'before-additive.txt' if additive else 'before.txt'),graphs('after-seed.txt' if seeded else 'after-additive.txt' if additive else 'after.txt')
assert before,'No graphs parsed'
if seeded:
    assert set(after)==set(before),'Unexpected graph addition/removal'
    def without_seed(text):
        # Reconstructing a caller invalidates only cached tooltip text.
        text=re.sub(r'PinToolTip="(?:\\.|[^"\\])*",','',text)
        return '\n'.join(line for line in text.splitlines() if not ('CustomProperties Pin (' in line and 'PinName="Seed"' in line))
    changed=[k for k,v in before.items() if k!='Stain Blade' and without_seed(after.get(k,''))!=without_seed(v)]
    assert not changed,('Unrelated graph changes; inspect before save',changed)
    assert 'BladeBloodSeedVariation' in after['Stain Blade'] and 'PinName="Seed"' in after['Stain Blade']
    print(f'Preserved {len(before)-1} other graphs (only new Seed pins on callers allowed)')
    (folder/'seed-graph-check.json').write_text(json.dumps({'preserved_graphs':len(before)-1,'after_sha256':hashlib.sha256((folder/'after-seed.txt').read_bytes()).hexdigest()}))
elif additive:
    assert set(after)==set(before),'Unexpected graph addition/removal'
    assert all(after.get(k)==v for k,v in before.items() if k!='Stain Blade'),'Unrelated graph changed; do not save'
    assert 'BladeBloodAccumulatedDepth' in after['Stain Blade']
    print(f'Preserved all {len(before)-1} other authored graphs verbatim; updated only Stain Blade')
    (folder/'additive-graph-check.json').write_text(json.dumps({'preserved_graphs':len(before)-1,'after_sha256':hashlib.sha256((folder/'after-additive.txt').read_bytes()).hexdigest()}))
else:
    assert set(after)-set(before)=={'Stain Blade'},set(after)-set(before)
    assert all(after.get(k)==v for k,v in before.items()),'An existing graph changed; do not save'
    print(f'Preserved all {len(before)} authored graphs verbatim; added only Stain Blade')
