from pathlib import Path
import re, posixpath, hashlib, json, math

root=Path(__file__).resolve().parents[2]
journal=root/'ProjectJournal.md'
old=journal.read_text(encoding='utf-8')
archive=root/'Docs/Journal/ProjectJournal-history-through-2026-09-26.md'
catalog=root/'Docs/Journal/CheckpointCatalog-20260926.md'
assert not archive.exists(), 'Do not overwrite an existing archive'
assert not catalog.exists(), 'Do not overwrite an existing catalog'

# Keep historical prose intact, rebasing relative Markdown links for its new location.
def rebase(m):
    url=m.group(2)
    if re.match(r'(?:[A-Za-z][\w+.-]*:|/|#)',url):return m.group(0)
    return m.group(1)+posixpath.normpath('../../'+url)+m.group(3)
archived=re.sub(r'(\]\()([^\s)]+)(\))',rebase,old)
archive.write_text('# Historical journal archive through September 26, 2026\n\n'
    'Superseded chronological record. Read [the current journal](../../ProjectJournal.md) first. '
    'Old current/pending statements and defaults are historical, not instructions to resume work. '
    'All pre-consolidation text is retained below; relative Markdown links were rebased.\n\n'
    f'Original UTF-8 text SHA-256 (normalized newlines): `{hashlib.sha256(old.encode()).hexdigest()}`.\n\n---\n\n'+archived,encoding='utf-8')
section=old.split('## Accepted checkpoints and pose contract',1)[1].split('- Policy cadence',1)[0]
catalog.write_text('# Accepted checkpoint provenance — September 26, 2026\n\n'
    'Preserved paths/hashes from the pre-consolidation journal; this pass did not rehash model binaries. '
    'For the current attack dropdown, stable enum identities and model exports, see '
    '[AttackCheckpointComparison](../AttackCheckpointComparison.md). For runtime contracts and current selection rules, '
    'see [the project journal](../../ProjectJournal.md#checkpoints-interpolation-and-parity).\n'+section,encoding='utf-8')

s=(root/'Saved/Diagnostics/ProjectJournal-current.md').read_text(encoding='utf-8')
s=s.replace('after the arm-return rotation controls and tick-260 fix','after the arm-return controls, tick-260 routing fix and left-elbow continuity fix')
s=s.replace('- Latest delivered work: right-arm kickback fixed; **Set Attack Arm Return Rotation Blend** added. Both compiled and loaded via Live Coding at **15:44:28 UTC September 26**. Thirteen current native tests passed at 15:45:13 UTC. See [arm-return contract and evidence](Docs/ArmReturn260AndRotationBlend.md).',
    '- Latest delivered work: **left-elbow snap during return fixed** by preserving bend/twist continuity, after the right-arm kickback fix and **Set Attack Arm Return Rotation Blend** node. Latest patch loaded via Live Coding at **16:19:12 UTC September 26**; all 14 current arm/core tests passed at 16:21:20 UTC. Same-state tick-163 rotation jump: 70.064 → 7.363 degrees, identical poses through 162. See [left-elbow diagnosis and evidence](Docs/ArmReturnLeftHandoff.md) and [rotation controls](Docs/ArmReturn260AndRotationBlend.md).')
s=s.replace('owned diagnostic Play ended; `Prophecy.SlashReturn.Audit=0`, `BodyRoute=1`, `Refined=1`','Play inactive; `Prophecy.SlashReturn.Audit=0`, `BodyRoute=1`, `Refined=1`, `ContinuousTwist=1`, `UnarmedShortestRotation=1`')
s=s.replace('Latest scene capture ran repeated pikes at approximately ticks 90/180/270; Pike\'s pelvis-position checkbox was true and both-arm return enabled for Pike.',
    'Latest scene capture ran one Pike starting at tick 90, ending at 121; Pike\'s pelvis-position checkbox and both-arm return were enabled, with Pelvis Local Rotation Blend 0.8 / Spine Local Rotation Blend 0. The earlier repeated-pike scene is historical.')
s=s.replace('wire the new node or push Git','wire the new node or push Git (the user subsequently wired the rotation node)')
s=s.replace('Elbow recovery solves coherent hinges at the final wrist before blending, with stable transport/degeneracy handling.',
    'Elbow recovery solves coherent hinges at the final wrist before blending. Active returns now track bend and axial-twist winding through ±180 degrees so interpolation cannot suddenly choose the opposite side; histories retire with the return. Stateless hand-chain callers retain their behavior. No new duration or inactive work.')
s=s.replace('- Latest causal test: unchanged prefix through 252;', '- Earlier right-arm causal test: unchanged prefix through 252;')
s=s.replace('Latest visual acceptance remains the user\'s decision.',
    'Latest visual acceptance remains the user\'s decision. The later left-elbow test preserved the exact prefix through 162 and reduced the 163 jump from 70.064 to 7.363 degrees; the full replay agrees. Sword clearance was nearly unchanged but slightly below the unit test metric (0.988), so do not infer universally collision-free motion.')
s=s.replace('References: [current controls and tick-260 fix]', 'References: [left-elbow continuity](Docs/ArmReturnLeftHandoff.md), [current controls and tick-260 fix]')
s=s.replace('switches only BodyRoute from 0 to 1 at 252.', 'switches only BodyRoute from 0 to 1 at 252. `hinge_latefix` similarly switches ContinuousTwist at 162; normal `hinge_final` is the full final replay.')
s=s.replace('- Analysis: `CompareArm260.py`', '- Latest elbow evidence: `left_stages` baseline, `hinge_latefix` causal capture, `hinge_final` final replay. `twist_latefix` is a rejected partial fix with a later 40-degree spike; do not reinstall it. `CompareLeftHandoff.py` measures axial rotation; `AnalyzeLeftSolve.py` splits raw/first/final solve contributions.\n- Analysis: `CompareArm260.py`')
s=s.replace('Latest queue has 14 tests because obsolete `ClearDirectPath` remains registered from an old live patch; **13** are current.', 'Latest queue has 15 tests because obsolete `ClearDirectPath` remains registered from an old live patch; **14** are current.')
s=s.replace('Normal diagnostic values: Audit 0, BodyRoute 1, Refined 1, UnarmedShortestRotation 1.', 'Normal diagnostic values: Audit 0, BodyRoute 1, Refined 1, UnarmedShortestRotation 1, ContinuousTwist 1. The latter now gates bend and axial-twist continuity together.')
s=s.replace('Docs/FKCoreTempering.md','Docs/CoreTempering.md').replace('Docs/AttackWarmup.md','Docs/EditorAttackWarmup.md')
s=s.replace('See [scope audit](Docs/SpecialRecovery.md).', 'See [scope audit](Docs/SpecialRecovery.md) and [upper-body exit inertia controls](Docs/UpperBodyAttackInertia.md).')
missing=[]
for url in re.findall(r'\]\(([^\s)]+)\)',s):
    if re.match(r'(?:[A-Za-z][\w+.-]*:|/|#)',url):continue
    if not (root/url.split('#')[0]).exists():missing.append(url)
assert not missing,missing
journal.write_text(s,encoding='utf-8')
print('Archived original; installed current journal:',len(old.split()),'->',len(s.split()),'words')
print('Current journal relative links validated')

for tag in ('hinge_latefix','hinge_final'):
    data=json.loads((root/f'Saved/Diagnostics/ArmReach/{tag}.json').read_text())
    def finite(x):
        if isinstance(x,float):assert math.isfinite(x)
        elif isinstance(x,dict):
            for y in x.values():finite(y)
        elif isinstance(x,list):
            for y in x:finite(y)
    finite(data)
    print(tag,'capture',data['reason'],'owned',data['owned'],'rows',len(data['rows']))
