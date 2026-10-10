from pathlib import Path
p=Path('Docs/GetUp.md');s=p.read_text(encoding='utf-8')
marker='The subsequent jiggle investigation'
history=s[s.index(marker):]
Path('Docs/Journal/GetUp-floor-correction-history-2026-10-10.md').write_text('# Removed get-up floor correction — historical evidence\n\nThe user requested removal of the automatic PHAT clearance lift and its toggle on October10,2026. This record is historical; do not restore the feature from these measurements. Current behavior: [GetUp](../GetUp.md).\n\n'+history,encoding='utf-8')
s=s[:s.index(marker)]
s=s.replace('Seven Blueprint nodes','Six Blueprint nodes').replace('All seven nodes','All six nodes')
s=s.replace('| Set Get Up Floor Correction | Enable/disable the automatic PHAT clearance lift for subsequent get-ups. Default enabled. |\n','')
a=s.index('To remove the automatic floor-height correction,');b=s.index('Handoff Alpha is normalized',a)
s=s[:a]+'The automatic PHAT floor-clearance lift and its toggle node were removed at the\nuser’s request on October10. Get Up retains the original clip-height alignment\nand explicit Ground Offset; no collider-support cache or per-sample height lift\nremains.\n\n'+s[b:]
a=s.index('decoder. With floor correction enabled,');b=s.index('At handoff,',a)
s=s[:a]+'decoder. '+s[b:]
s=s.replace('implementation. Clearance covers published skeleton bodies, not the held sword\nor arbitrary obstacles. It uses the captured floor plane without recurring traces.','implementation.')
s+='The removed floor-correction experiment and toggle validation are preserved as\n[historical evidence](Journal/GetUp-floor-correction-history-2026-10-10.md). They do\nnot describe an available feature.\n'
p.write_text(s,encoding='utf-8')
