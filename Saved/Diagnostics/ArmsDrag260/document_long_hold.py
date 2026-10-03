from pathlib import Path

root=Path(__file__).resolve().parents[3]
p=root/'Docs/ArmRepellantCone.md'
s=p.read_text(encoding='utf-8')
needle='Current-setup investigation, September30:'
assert s.count(needle)==1
entry='''**Long-hold quaternion defect fixed, September30:** increasing Hold Out Time to2.5s exposed a defect that the earlier0.5s fade did not. At tick249 the solver requested5.708538degrees but the old shortest-quaternion-arc intersection produced50.278601degrees. Its invalid intersection parameter was clamped to the arc endpoint, after which recoil assumed the intended damped twist had been reached. The wrist jumped47.267877degrees in one NN update, then43.170805degrees back. Damping now separates horizontal twist from the remaining swing, interpolates the twist-free swing, and recomposes the exact accepted twist. No iterative solve, extra inference, layout changes, positional edits or left-wrist work. The no-swing-damping path still applies pure horizontal recoil to the current proposed orientation.

Live Coding loaded18:55:33UTC. All11 focused cone tests passed18:57:03UTC, including mirrored opposite-orientation regression, quaternion-sign invariance, partial/zero influence, horizontal elevation and full-orientation damping. Matched350-tick replay at unchanged cone150/wrist60000/limit5/damping10/hold2.5/blend0.5: tick249 step47.267877→6.412931degrees, tick251 step43.170805→14.583379degrees; maximum235–280 step47.267877→14.583379degrees. Requested/realized twist agrees within0.000008degrees. All six arm joint positions, future AND presented, match exactly; left wrist rotations match within0.000003degrees. Evidence: `Saved/Diagnostics/ArmsDrag260/wrap_long270.json`, `wrap_long270_fixed.json`, native logs, `long_hold_analysis.json` and `compare_long_hold.py`.

**Limit of this fix:** the held pose at270 is not eliminated: before/after right wrist orientation there differs by only0.847704degrees. The trace confirms full influence at270, accepted twist approximately−5.5degrees versus raw proposal approximately−145degrees. With upper release191 and hold2.5s, full influence is intended until approximately341, then0.5s fade. This repair removes the demonstrated quaternion spike; it does not redefine the outgoing spine-local reference, tighten the soft limit, change the user's timing or claim that every held posture looks natural. Owned PIE ended18:57:32UTC and all five audit CVars restored0. No Blueprint changes/save, full suite or push this turn.

Earlier short-hold investigation, September30:'''
s=s.replace(needle,entry)
s=s.replace('**Wrist-orientation stop correction, September29:**','**Earlier wrist-orientation stop correction, September29 (arc solver superseded by the long-hold fix above):**')
p.write_text(s,encoding='utf-8')
p=root/'ProjectJournal.md';s=p.read_text(encoding='utf-8')
needle='## Resume here\n\n';assert needle in s
entry='''- **Long-hold wrist quaternion spike fixed (September30):** user increased hold to2.5s, wrist recoil60000/limit5/damping10. At249 the old quaternion-arc intersection requested5.708538degrees but realized50.278601degrees, causing47.27degrees outward then43.17degrees back. Replaced invalid full-arc intersection with separated horizontal twist/swing damping; accepted twist now exact within0.000008degrees. Live Coding18:55:33UTC; all11 focused cone tests passed18:57:03, including mirrored antipodal/sign/partial-alpha regression. Same350-tick replay reduces249/251 steps to6.41/14.58degrees; all six arm joint positions match exactly (future/presented), left wrist unchanged. The270 held pose itself remains (only0.85degrees different): influence is still100%, accepted around−5.5 versus raw around−145degrees; configured2.5s hold ends approximately341 after upper release191. Do not claim the held pose was removed; the measured quaternion spike was fixed. Earlier short-hold investigation below did not expose this defect. Disabled guards, reference/timing, right-only ownership and no recurrent wrist feedback retained; no BP edits/save/full suite/push. Owned PIE ended18:57:32, five audits0. Evidence Saved/Diagnostics/ArmsDrag260/long_hold_analysis.json and wrap_long270[_fixed] captures. [Details](Docs/ArmRepellantCone.md).

'''
s=s.replace(needle,needle+entry,1)
s=s.replace('Current wrap investigation: cone strength150','Earlier short-hold wrap investigation (superseded for the longer hold above): cone strength150',1)
p.write_text(s,encoding='utf-8')
print('Updated cone documentation and journal')
