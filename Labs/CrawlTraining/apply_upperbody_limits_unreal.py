"""Apply the explicit current crawl upper-body limit plan through Unreal's existing Python API.

Run through Tools/RunUnrealRemote.py. Refuses active Play, a dirty PHAT,
changed source fingerprints, or any unexpected export change. Saves only PHAT.
"""
import hashlib
import json
import re
import shutil
import argparse
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
parser=argparse.ArgumentParser();parser.add_argument('--resume-rolled-back',action='store_true')
args=parser.parse_args()
out=root/'Saved/MimicKitCrawl/upperbody-limits-20261017'
canonical=root/'Saved/MimicKitUEFN'
plan=json.loads((out/'limit-plan.json').read_text(encoding='utf-8'))
assert plan['margin_factor']==1.05
for name,digest in plan['motion_sha256'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
assert all(not row['source_body'].startswith(('thigh','calf','foot')) for row in plan['joints'])
sub=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert sub.get_game_world() is None, 'User Play is active; leave it untouched'
pa=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin')
dirty=lambda:sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
before_dirty=dirty();pa_package=pa.get_outermost().get_path_name()
if pa_package in before_dirty:
    assert args.resume_rolled_back,'PHAT has unsaved user edits'
    # Only recover our own verified rollback; exact live/source equality below
    # and the unchanged on-disk backup are required before any further edit.
    assert (out/'before/live-rig.json').exists()
    before_dirty.remove(pa_package)
for name,info in plan['source_files'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==info['sha256'],name
assert hashlib.sha256((root/'Labs/MimicKitUEFN/limits.json').read_bytes()).hexdigest()==plan['limits_sha256']
backup=out/'before';backup.mkdir(exist_ok=True)
assetfile=root/'Content/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.uasset'
if (backup/assetfile.name).exists():
    assert (backup/assetfile.name).read_bytes()==assetfile.read_bytes(),'Existing backup differs from current asset'
else:shutil.copy2(assetfile,backup/assetfile.name)
for name in ('limits.json','humanoid_uefn.xml','humanoid_uefn_physics.xml','physics.json'):
    shutil.copy2(root/'Labs/MimicKitUEFN'/name,backup/name)
shutil.copy2(root/'Saved/Robotics/rig.json',backup/'historical-rig.json')
shutil.copy2(canonical/'source-rig.json',backup/'source-rig.json')
shutil.copy2(root/'Labs/MimicKitUEFN/overlay-data.json',backup/'overlay-data.json')

def export(name):
    unreal.SystemLibrary.execute_console_command(sub.get_editor_world(),'Prophecy.Robotics.ExportRig '+name)
    data=json.loads((root/'Saved/Robotics'/name).read_text(encoding='utf-8-sig'))
    assert data['success'],data.get('error')
    return data

prefix='crawl-upperbody-20261017'
before=export(prefix+'-before-limits.json')
expected=json.loads((canonical/'source-rig.json').read_text())
assert before=={k:v for k,v in expected.items() if k!='source_files'},'Live PHAT differs from fitted source'
(backup/'live-rig.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
byname={j['name']:j for j in before['joints']}
modes={0:unreal.AngularConstraintMotion.ACM_FREE,1:unreal.AngularConstraintMotion.ACM_LIMITED,2:unreal.AngularConstraintMotion.ACM_LOCKED}
lib=unreal.ConstraintInstanceBlueprintLibrary
changes=[j for j in plan['joints'] if j['changed']]
for row in changes:
    j=byname[row['source_joint']]
    assert j['angular_modes_twist_swing2_swing1']==row['old_modes']
    assert max(abs(a-b) for a,b in zip(j['angular_limits_deg_twist_swing2_swing1'],row['old_degrees']))<1e-5

def set_row(row,version):
    m=row[version+'_modes'];a=row[version+'_degrees']
    lib.set_angular_limits(pa.get_constraint_by_name(row['source_joint']),modes[m[2]],a[2],modes[m[1]],a[1],modes[m[0]],a[0])

def stripped(j):
    j=dict(j)
    for key in ('angular_modes_twist_swing2_swing1','angular_limits_deg_twist_swing2_swing1'):j.pop(key)
    # Unreal omits default-valued fields (e.g. zero locked twist) entirely.
    # Remove only the six authorized angular fields, including their comma.
    j['original_profile_text']=re.sub(r'\b(Swing1LimitDegrees|Swing2LimitDegrees|TwistLimitDegrees|Swing1Motion|Swing2Motion|TwistMotion)=[^,()]+,?', '',j['original_profile_text'])
    return j

applied=[]
try:
    for row in changes:set_row(row,'new');applied.append(row)
    after=export(prefix+'-after-limits.json')
    assert {k:v for k,v in before.items() if k!='joints'}=={k:v for k,v in after.items() if k!='joints'},'Non-joint export data changed'
    changed_names={j['source_joint'] for j in changes}
    for a,b in zip(before['joints'],after['joints']):
        assert stripped(a)==stripped(b),a['name']
        if a['name'] not in changed_names:assert a==b,a['name']
    for row in changes:
        j=next(j for j in after['joints'] if j['name']==row['source_joint'])
        assert j['angular_modes_twist_swing2_swing1']==row['new_modes']
        assert max(abs(a-b) for a,b in zip(j['angular_limits_deg_twist_swing2_swing1'],row['new_degrees']))<1e-4
except Exception:
    for row in applied:set_row(row,'old')
    raise
assert unreal.EditorAssetLibrary.save_loaded_asset(pa,only_if_is_dirty=False),'PHAT save failed'
assert dirty()==before_dirty,'Unrelated dirty package state changed'
sources={}
for name in plan['source_files']:
    p=root/name;sources[name]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
after['source_files']=sources
(canonical/'source-rig.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
assert sub.get_game_world() is None
receipt=dict(saved_asset=pa.get_path_name(),changed_constraints=len(changes),source_files=sources,
             dirty_packages_preserved=before_dirty,non_limit_export_fields_unchanged=True,leg_profiles_unchanged=True,backup=str(backup),changes=changes)
(out/'applied-limits.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
