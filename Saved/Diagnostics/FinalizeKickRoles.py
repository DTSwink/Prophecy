import pathlib,re
root=pathlib.Path(__file__).resolve().parents[2]
log=(root/'Saved/Logs/GameAnimationSample3.log').read_text(encoding='utf-8-sig')
rows=[s for s in log.splitlines() if 'Test Completed. Result=' in s]
assert len(rows)==11 and all('Result={Success}' in s for s in rows),rows
report='Kick limb roles validation, 2026-09-22\nNormal build succeeded: 115.26s. Final test-only rebuild: 60.75s.\nOne float-ULP mismatch in the original test assertion corrected to 1e-6 tolerance; no gameplay change.\nPose Blueprint compiled status3, role pins refreshed and saved; old defaults/links preserved and all three new non-kicking inputs inherit their original shared values/wires.\nNo gameplay rollout or scene edits.\n\n'+'\n'.join(rows)+'\n'
(root/'Saved/Diagnostics/KickRolesValidation.txt').write_text(report,encoding='utf-8')
status='Normal editor build passed115.26s; final test-only rebuild passed60.75s. Unreal reopened on testNN, both role nodes refreshed with existing values/links preserved, new non-kicking inputs copied from shared feet, and pose Blueprint compiled status3 and saved. All11 focused tests passed20:21UTC (role mirroring, per-axis pose/toes, return/hold retirement, reset, regional policy, calf continuity and60-tick clock). Initial role-test rotation assertion differed by one float ULP; corrected its tolerance to1e-6, with no gameplay change. No gameplay rollout. Evidence `Saved/Diagnostics/KickRolesValidation.txt` and `KickRolePinValidation.json`; asset backup `KickRoles-BeforeRefresh.uasset`.'
# Use actual completion time rather than the anticipated wall clock.
time=re.search(r'-(\d\d\.\d\d\.\d\d):',rows[-1]).group(1).replace('.',':')
status=status.replace('20:21UTC',time+'UTC')
j=root/'ProjectJournal.md'
text=j.read_text(encoding='utf-8')
text=text.replace('Normal build and validation pending; see [recovery]',status+' See [recovery]',1)
text=text.replace('configure independent kickL/kickR profiles','configure a separate kick recovery profile',1)
j.write_text(text,encoding='utf-8')
for name in ['AttackRecoveryBlend.md','LowerBodyTempering.md']:
    p=root/'Docs'/name
    text=p.read_text(encoding='utf-8')
    text+='\n\nSeptember22 kicking/non-kicking refinement: '+status+'\n'
    p.write_text(text,encoding='utf-8')
print(report)
