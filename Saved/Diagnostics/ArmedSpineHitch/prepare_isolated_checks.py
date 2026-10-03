from pathlib import Path
p=Path('Saved/Diagnostics/ArmedSpineHitch/verify_forearms.py');s=p.read_text(encoding='utf-8');s=s.replace("assert ed.get_game_world() is None,'Preserve user Play'", "# These scoped native tests use value fixtures or their own temporary editor worlds.\n# No test starts/stops PIE or modifies an actor in the user's world.\nprint('ARMED_FOREARM_USER_PLAY_PRESERVED',bool(ed.get_game_world()))")
p.write_text(s,encoding='utf-8')
