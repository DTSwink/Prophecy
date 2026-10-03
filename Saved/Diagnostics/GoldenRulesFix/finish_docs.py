from pathlib import Path
p=Path('Saved/Diagnostics/GoldenRulesFix/update_docs.py');src=p.read_text(encoding='utf-8-sig');exec(src[src.index("p=Path('ProjectJournal.md')"):])
for name in ['Docs/BlendTickTiming.md','Docs/KickPoleHandoffs20261002.md','Docs/GoldenRulesAuditFix20261002.md']:
 p=Path(name);data=p.read_bytes()
 try:data.decode('utf-8')
 except UnicodeDecodeError:p.write_text(data.decode('cp1252'),encoding='utf-8')
