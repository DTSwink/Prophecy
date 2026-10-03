"""Reuse the reviewed fresh registry exporter with explicit final-fight roots."""
import json
import os
import runpy
from datetime import datetime
from pathlib import Path
import unreal

roots = ['/Game/_mygame/SKM_UEFN_Mannequin',
         '/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin',
         '/Game/Prophecy/Materials/M_ProphecyBloodVFX_Surface',
         '/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle',
         '/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest',
         '/Game/_mygame/blood2/MI_blooddecal',
         '/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop',
         '/Game/Input/TIS_MobileControls',
         '/Game/_mygame/sword/A_Sword',
         '/Game/_mygame/sword/geometry/Sword_GL01_Training',
         '/Engine/BasicShapes/Cube', '/Game/testNN']
saved = Path(unreal.Paths.project_saved_dir()).resolve()
target = saved/'JoltMigration'/('FightCookRegistry-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
overrides = {'PROPHECY_COOK_REGISTRY_OUTPUT': str(target),
             'PROPHECY_COOK_REGISTRY_ROOTS_JSON': json.dumps(roots)}
previous = {key: os.environ.get(key) for key in overrides}
try:
    os.environ.update(overrides)
    runpy.run_path(str(saved/'JoltMigration/CookDependencyRevisionDraft/Export-FreshCookRegistry.py'))
finally:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
report = json.loads(target.read_text(encoding='utf-8'))
print('FIGHT_COOK_REGISTRY', str(target))
print(json.dumps({'packages': report['packageCount'], 'runtime_game_packages': len(report['runtimeGamePackageClosure']),
                  'runtime_external_packages': len(report['runtimeExternalPackageClosure']),
                  'source_bytes': sum(f['bytes'] for f in report['files']), 'success': report['success']}, indent=2))
