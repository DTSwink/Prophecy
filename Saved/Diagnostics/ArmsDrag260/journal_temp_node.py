from pathlib import Path
p=Path('ProjectJournal.md');s=p.read_text(encoding='utf-8')
anchor='[Contract and evidence](Docs/ArmRepellantCone.md).'
assert anchor in s
s=s.replace(anchor,anchor+' Temporary **TEMP Set Pre Drag Fix Version** node added for the user\'s visual comparison: per-agent Use Previous Version=true restores pre-both-fixes full-upper recurrent feedback plus wrist-driven forearm roll; false/current is the initial default. Configure before the attack and replay/reset because history is not rewound. Repeated calls preserve recovery timing; reset snapshots include the switch. No Blueprint wiring/settings changed. Remove this temporary path after the comparison.',1)
p.write_text(s,encoding='utf-8')
