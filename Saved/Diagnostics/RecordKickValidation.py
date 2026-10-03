from pathlib import Path
r=Path(__file__).resolve().parents[2]
log=(r/'Saved/Logs/GameAnimationSample3.log').read_text(encoding='utf-8',errors='replace')
results=[line for line in log.splitlines() if 'Test Completed.' in line]
assert len(results)==6 and all('Result={Success}' in x for x in results),results
(r/'Saved/Diagnostics/KickProfilesValidation.txt').write_text('\n'.join(results)+'\nNormal build: 108.36s, succeeded.\nThree recovery nodes refreshed; other values/links preserved; pose BP status=3 and saved.\nNo gameplay rollout.\n')
p=r/'ProjectJournal.md';s=p.read_text(encoding='utf-8')
s=s.replace('Normal editor build passed108.36s after user-authorized restart; startup is rebuilding missing engine shaders. Blueprint refresh and focused runtime checks pending;', 'Normal editor build passed108.36s after user-authorized restart; testNN reopened. Startup rebuilt missing cached engine shaders. Both reflected nodes verified; three recovery nodes refreshed with other values/links preserved, pose BP compiled status3 and saved. All six focused tests passed19:14:49UTC (KickProfiles, AttackRecovery, ReturnTimeline, SeparateReturns, SixtyTickClock, actual Jolt AttackCollisionPhases). Collision checks cover simulated/attached swords, native owner-pair restoration at Hit, retained active-attack context, repeated refresh and unchanged body/joint counts. No gameplay rollout or scene changes. Evidence `Saved/Diagnostics/KickProfilesValidation.txt`; before-refresh BP backup `Saved/Diagnostics/KickProfiles-BeforeRefresh.uasset`;')
s=s.replace('Include this patch in the next normal build before reopening. [Input contract]', 'Included in the108.36s normal kick-profile build on September22. [Input contract]')
p.write_text(s,encoding='utf-8')
for name in ['AttackRecoveryBlend.md','LowerBodyTempering.md','SwordAttackCollision.md']:
    p=r/'Docs'/name
    s=p.read_text(encoding='utf-8')
    s+='''
September22 kick-profile/Hit validation: normal editor build succeeded (108.36s),
testNN reopened, both new nodes reflected, and all three existing recovery nodes
refreshed with other values/connections preserved. Pose Blueprint compiled and saved.
Six focused tests passed at19:14:49UTC: KickProfiles, AttackRecovery, ReturnTimeline,
SeparateReturns, SixtyTickClock, and Jolt Sword AttackCollisionPhases. The latter
checks native owner-pair restoration at Hit for simulated and attached swords,
retained attack context, repeated refresh, and stable body/joint counts. No scene
rollout. Evidence: `Saved/Diagnostics/KickProfilesValidation.txt`.
'''
    p.write_text(s,encoding='utf-8')
