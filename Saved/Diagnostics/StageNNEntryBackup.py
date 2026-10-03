import ast,json,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
def git(*args):
    r=subprocess.run(['git',*args],cwd=root,capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr)
    return r.stdout
assert not git('diff','--cached','--name-only').strip(),'Existing staged work must be preserved'
changed=git('diff','--name-only','--','Source','Tools/NN','Docs','ProjectJournal.md').splitlines()
new=git('ls-files','--others','--exclude-standard','--','Source','Tools/NN','Docs').splitlines()
def wanted(f):
    return not ('JoltBlood' in f or f.startswith('Docs/JoltBlood'))
selected=sorted(set(f for f in changed+new if wanted(f)))
selected.append('Content/_mygame/locomotion/BP_ProphecyManualPoseAgent.uasset')
scripts=['Saved/Diagnostics/CaptureHead505.py','Saved/Diagnostics/CaptureNNEntry.py',
 'Saved/Diagnostics/RunNNEntryChecks.py','Saved/Diagnostics/RunHeadEntryChecks.py',
 'Saved/Diagnostics/NNEntry20261003/analyze.py','Saved/Diagnostics/NNEntry20261003/verify_handoff.py',
 'Saved/Diagnostics/Head50520261003/compare_fixed.py','Saved/Diagnostics/Head50520261003/analyze_residual.py',
 'Saved/Diagnostics/Head50520261003/verify_final.py']
selected+=scripts
for f in selected:
    p=root/f
    if not p.exists():continue # selected tracked deletion
    limit=8*1024*1024 if f.endswith('.uasset') else 1024*1024
    assert p.stat().st_size<limit,(f,p.stat().st_size)
    assert p.suffix not in ['.onnx','.pt','.umap','.dll','.pdb','.zip','.png','.jsonl']
    if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8-sig'),filename=f)
git('add','--',*sorted(set(selected)-set(scripts)))
git('add','-f','--',*scripts)
staged=git('diff','--cached','--name-only').splitlines()
assert set(staged)==set(selected),(set(staged)-set(selected),set(selected)-set(staged))
git('diff','--cached','--check')
receipt={'paths':staged,'count':len(staged),'working_tree_bytes':sum((root/f).stat().st_size for f in staged if (root/f).exists())}
(root/'Saved/Diagnostics/NNEntry20261003/push-manifest.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
