from pathlib import Path
p=Path('Docs/ArmRepellantCone.md');s=p.read_text(encoding='utf-8')
start=s.index('- **TEMP Set Pre Drag Fix Version**:')
end=s.index('- **Set Arm Repellant Cone**:',start)
s=s[:start]+s[end:]
s=s.replace('### Wrist twist recoil\n','### Wrist twist recoil\n\nWrist recoil and its debug arc now apply to the **right hand only**. The left wrist is left to its separate hand constraint. The upper-arm cone still applies to both arms. The temporary pre-drag comparison node and implementation have been removed; corrected behavior is permanent.\n',1)
p.write_text(s,encoding='utf-8')
p=Path('ProjectJournal.md');s=p.read_text(encoding='utf-8')
start=s.index(' Temporary **TEMP Set Pre Drag Fix Version** node added')
end=s.index('\n',start)
s=s[:start]+' Temporary pre-drag comparison node/path removed at the user\'s request; corrected (former false) behavior retained. Wrist recoil and its debug arc now apply to the right hand only; left-hand constraint and the bilateral upper-arm cone retain ownership.'+s[end:]
p.write_text(s,encoding='utf-8')
