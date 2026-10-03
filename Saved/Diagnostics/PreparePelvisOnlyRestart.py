from pathlib import Path
p=Path('Saved/Diagnostics/SaveCloseFootEntry.py');s=p.read_text();s=s.replace('BP-BeforeFootEntryRestart.uasset','BP-BeforePelvisOnlyRollback.uasset').replace('FootEntry-Restart.json','PelvisOnly-Restart.json').replace('FOOT_ENTRY_BP_SAVED_RESTARTING','PELVIS_ONLY_ROLLBACK_SAVED_RESTARTING');Path('Saved/Diagnostics/SaveClosePelvisOnly.py').write_text(s)
