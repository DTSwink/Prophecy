"""Assert the actual Blueprint/Jolt capture, independent of the setup script."""
import json,math,pathlib
out=pathlib.Path(__file__).resolve().parents[2]/'Saved/Diagnostics/SpearPike20261030'
data=json.loads((out/'play.json').read_text());assert data['error'] is None,data['error']
result={}
for mode in ('forward','withdraw','slash','resistance','flesh'):
    rows=[r for r in data['samples'] if r['mode']==mode]
    assert len(rows)>30,(mode,len(rows))
    assert math.dist(rows[0]['prelaunch_velocity'],[0,0,0])<.01,'Inherited test launch still active'
    assert all(math.isfinite(x) for r in rows for x in r['position']+r['velocity'])
    cuts=[r for r in rows if r['cuts']]
    if mode=='slash':
        assert not cuts,'Side impact admitted a cut'
        assert any(r['velocity'][1]<500 for r in rows[5:]),'Side collision did not respond'
        result[mode]={'cut_count':0,'collision_responded':True};continue
    assert cuts and all(r['type']==0 for r in cuts),(mode,'Missing pike admission')
    assert all(r['damping']==([0,0,0] if mode in ('forward','withdraw') else [100,10,1]) for r in cuts),(mode,'Fixture damping mismatch')
    if mode=='resistance':
        assert cuts[-1]['t']-cuts[0]['t']>5/60,'Did not cover the original delayed cap'
        assert abs(cuts[-1]['velocity'][2])<abs(cuts[0]['velocity'][2])*.8,'Authored material resistance not effective'
        audit=json.loads((out/'play-resistance-joint.json').read_text(encoding='utf-8-sig'))
        joints=[c for c in audit['constraints'] if c['jolt'] and 'A_Spear_C_3.' in c['component']]
        assert len(joints)==1,joints
        axis=joints[0]['translation'][2]
        assert axis['motion']==1 and axis['damping']==100 and axis['velocity_drive'],axis
        result[mode]={'cut_seconds':cuts[-1]['t']-cuts[0]['t'],'axial_motion':'Free','damping':100,'final_speed':math.dist(rows[-1]['velocity'],[0,0,0])}
        continue
    assert mode in data['released'],(mode,'Cut never released')
    released=next(r for r in rows if r['t']>=data['released'][mode])
    last=next(r for r in reversed(rows) if r['cuts'] and r['t']<released['t'])
    def axial(row):
        return sum((w-p)*a for w,p,a in zip(last['wound_position'],row['position'],row['axis']))-row['root']
    if mode=='withdraw':
        assert axial(released)>released['length']+.05,(mode,axial(released))
    else:
        threshold=released['rear']-released['root']-15-.05
        assert last['axial']>=threshold-.002,(mode,'Released late or frame capture mismatch')
        assert axial(released)<threshold,(mode,'Released before rear clearance')
    assert not rows[-1]['wound'] and rows[-1]['cuts']==0,(mode,'Cleanup incomplete')
    if mode=='flesh':
        # NullRHI does not instantiate Niagara rendering. Verify cut, stain
        # callback and cleanup here; this is not a visual-effects approval.
        assert all(r['matter']==2 for r in cuts),'Fixture missed flesh'
        assert max(r.get('stain_depth',0) for r in rows)==1,'Blade stain did not reach full depth'
        assert rows[-1]['collision_type']==rows[0]['collision_type'],'Flesh collision policy not restored'
        assert all('T_ImperialSpear_BaseColor' in r['base_color_texture'] for r in rows if 'base_color_texture' in r),'Blood replaced the spear material'
    result[mode]={'admitted':data['first'][mode],'released':data['released'][mode],'release_axial_cm':axial(released),'wound_cleaned':not rows[-1]['wound']}
(out/'play-verified.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
