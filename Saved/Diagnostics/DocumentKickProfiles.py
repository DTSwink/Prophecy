from pathlib import Path
r=Path(__file__).resolve().parents[2]
p=r/'Docs/AttackRecoveryBlend.md';s=p.read_text();a=s.index('**Force Run**');b=s.index('For kickR,',a)
s=s[:a]+'''`Set Kick To Locomotion Blend` has the same regional Source/Hold/Blend controls.
After kickL/kickR, the agent automatically selects that profile. Other attacks use
`Set Attack To Locomotion Blend`. Until the kick setter is called, kicks retain the
regular profile. A regular setter in On Attack Ended cannot overwrite an explicitly
configured kick handoff; the matching setter can still configure that handoff before
its first prediction. No new per-frame selection or additional clock is introduced.

The redundant **Force Run** pin has been removed. Each region's **Source** is now
the sole choice; set that region to Run when needed. Existing Source connections,
holds and blend durations are retained when nodes are refreshed.

'''+s[b:];p.write_text(s)
p=r/'Docs/LowerBodyTempering.md';s=p.read_text();i=s.index('\n')+1
s=s[:i]+'''
## Separate kick recovery profile

`Set Kick Locomotion Lower Body Tempering` stores the same Enabled, feet XY/Z/rotation
and pelvis XY/Z/rotation controls separately. It is selected automatically when
kickL/kickR returns to locomotion, before On Attack Ended runs. The regular setter
configures the normal profile; during a kick handoff it cannot overwrite the kick
profile. A kick setter called during that handoff applies immediately. Configure
both profiles in BeginPlay, then use the existing **Blend Locomotion Lower Body
Tempering To Normal** in On Attack Ended to blend from whichever profile was selected.
Feet/pelvis holds and durations remain independent and use 60 unpaused game ticks
per authored second. The kick setter does not create its own return schedule.

Until a kick profile is configured, the old immediate-set behavior is unchanged.
Once configured, a non-kick attack exit selects the last regular profile. Disabled
or all-one kick settings explicitly disable kick recovery tempering; they do not
fall back to the regular values. Completed return blends remove active values and
timelines, while keeping the configured profiles for the next attack. Active
specials still bypass tempering, and knee reconstruction/pinning math is unchanged.
Reset cancels active blends and clears the selected kick context before restoring
its captured tempering values. Profile storage adds no ticking or inference.

'''+s[i:];p.write_text(s)
p=r/'Docs/SwordAttackCollision.md';s=p.read_text();s=s.replace('The existing owner-body exclusions are separate: an attacking sword still ignores its wielder as before.','''Owner-body exclusions are separate: the sword ignores its wielder until the first
NN **Hit** output, then restores normal sword-owner contact during the remaining
attack animation. The gripping-hand exclusion remains. This is latched for every
attack family, including equipment/rebinding after Hit; it does not switch off
attack sweeps, special solver iterations or attack physical profiles. Stops,
interruptions and completion still restore normally if Hit never occurs. Body-body
PHAT self-collision and explicit Blueprint pair exclusions are unchanged.''');p.write_text(s)
