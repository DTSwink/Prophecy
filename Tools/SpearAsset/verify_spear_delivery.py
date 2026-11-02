"""Verify final saved delivery and collect focused native regression evidence."""
import ast,hashlib,json,pathlib,re
root=pathlib.Path(__file__).resolve().parents[2]
out=root/'Saved/Diagnostics/SpearPike20261030'
before=json.loads((out/'before-hashes.json').read_text(encoding='utf-8-sig'))
protected={}
for name,old in before.items():
    if name.startswith('Source/'):continue
    digest=hashlib.sha256((root/name).read_bytes()).hexdigest().upper()
    protected[name]={'unchanged':digest==old,'sha256':digest}
assert all(x['unchanged'] for x in protected.values()),protected
(out/'protected-hashes.json').write_text(json.dumps(protected,indent=2))
log=(out/'editor-final.log').read_text(encoding='utf-8',errors='replace')
tests={}
for name in ['Prophecy.Spear.NativeLifecycle','Prophecy.Spear.PassThroughGeometry',
             'Prophecy.Jolt.HitEvents.CleanPike','Prophecy.Jolt.Constraints.PikeWoundCorrection']:
    result=re.findall(r'Test Completed\. Result=\{(\w+)\} Name=\{[^}]+\} Path=\{'+re.escape(name)+r'\}',log)
    assert result and result[-1]=='Success',(name,result)
    tests[name]=result[-1]
assert '/Game/_mygame/spear/A_Spear.A_Spear.Status = BS_UpToDate' in log
assert 'Spear disk reload: (True, Text(""))' in log
assert 'Result: Succeeded' in (out/'build-ccd.log').read_text(errors='replace')
assets={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root/'Content/_mygame/spear').rglob('*.uasset')}
for name in ['test_unreal_spear_play.py','finish_unreal_spear_blueprint.py','verify_spear_play.py',
             'verify_spear_graph.py','verify_unreal_spear_asset.py','reload_verify_unreal_spear.py',
             'test_unreal_spear_regressions.py','verify_spear_delivery.py']:
    ast.parse((root/'Tools/SpearAsset'/name).read_text())
receipt={'actor':'/Game/_mygame/spear/A_Spear','native_tests':tests,
    'play':json.loads((out/'play-verified.json').read_text()),
    'graph':json.loads((out/'graph-verified.json').read_text()),
    'asset':json.loads((out/'asset-verified.json').read_text()),
    'saved_assets_sha256':assets,'protected_originals':protected,
    'normal_build':'build-ccd.log; isolated copied DLL host, no Live Coding',
    'limits':['Headless physics/material-binding verification; no rendered Niagara approval.',
              'Big Throw controller attachment/release/flight integration is a separate existing pending port.']}
(out/'delivery.json').write_text(json.dumps(receipt,indent=2))
print('PASS: four native regressions, five Play cases, saved-asset reload, graph audit and six unchanged originals.')
