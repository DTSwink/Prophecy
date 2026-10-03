from pathlib import Path
import re
s=Path('Saved/Logs/GameAnimationSample3.log').read_text(encoding='utf-8',errors='replace');s=s[s.rfind('LogPython: ARMED_FOREARM_CHECKS'):]
lines=[l for l in s.splitlines() if 'Test Completed.' in l or 'Automation Test Queue Empty' in l or 'LogAutomationController: Error' in l or 'No tests found' in l]
print('\n'.join(lines));Path('Saved/Diagnostics/ArmedSpineHitch/forearm-tests.log').write_text('\n'.join(l for l in s.splitlines() if 'Automation' in l),encoding='utf-8')
