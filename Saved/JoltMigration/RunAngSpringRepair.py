"""Invoke the isolated editor helper; it never saves a Blueprint asset."""
import json
import sys
from pathlib import Path
import unreal

mode = sys.argv[1]
assert mode in ('Inspect', 'Repair', 'RepairLibrary')
label = sys.argv[2] if len(sys.argv) > 2 else mode.lower()
assert label in ('inspect', 'inspect_library', 'repair')
target = Path.home() / '.codex/tmp/ProphecyJolt/AngSpringRepair-20260910' / (label + '.json')
assert not target.exists()
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
unreal.SystemLibrary.execute_console_command(world, f'Prophecy.Editor.AngSpringWorldContext {mode} {target.as_posix()}')
report = json.loads(target.read_text(encoding='utf-8-sig'))
local = Path(unreal.Paths.project_saved_dir()).resolve() / 'JoltMigration/AngSpringRepair-20260910' / target.name
assert not local.exists()
local.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key not in ('before', 'after', 'library_entries_with_user_defined_world_context', 'entries', 'library_before', 'library_after', 'repaired_entries')}, indent=2))
for phase in ('before', 'after'):
    if phase in report:
        data = report[phase]
        print(phase, json.dumps({key: data[key] for key in ('user_defined_pins', 'actual_context_pins', 'graph_nodes', 'remaining_pins_and_wires_md5')}, indent=2))
assert report['success'], report['error']
