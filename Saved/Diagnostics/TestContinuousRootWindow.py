import unreal, json, pathlib, time, traceback
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world(), 'Run this focused check with PIE stopped'
out = pathlib.Path(unreal.Paths.project_saved_dir()) / 'Diagnostics/ContinuousRootWindowPIE.json'
s = {'start': time.monotonic(), 'rows': [], 'subframe_advances': 0, 'max_error_cm': 0.0}
def unpack(value):
    assert value is not None, 'Getter returned false'
    if len(value) == 3:
        assert value[0]
        return value[1], value[2]
    return value
def xyz(v): return [v.x, v.y, v.z]
def finish(result, error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world(): level.editor_request_end_play()
    out.write_text(json.dumps({'result': result, 'error': error, 'subframe_advances': s['subframe_advances'],
        'max_current_error_cm': s['max_error_cm'], 'rows': s['rows']}, indent=2))
    print('CONTINUOUS_ROOT_WINDOW_TEST', result, error)
def tick(_):
    try:
        assert time.monotonic() - s['start'] < 60, 'Timeout'
        w = ed.get_game_world()
        if not w or unreal.GameplayStatics.get_time_seconds(w) < .6: return
        a = unreal.GameplayStatics.get_player_pawn(w, 0)
        roots, times = unpack(unreal.ProphecyRootPhysicsLibrary.get_continuous_locomotion_root_window(a))
        raw, rawtimes = unpack(a.get_locomotion_root_window())
        assert len(roots) == 9 and len(times) == 9 and len(raw) == 10
        assert abs(times[0]) < 1e-8 and all(times[i] > times[i-1] for i in range(1,9))
        p, current = roots[0].translation, a.get_root_low_point()
        error = ((p.x-current.x)**2 + (p.y-current.y)**2 + (p.z-current.z)**2)**.5
        s['max_error_cm'] = max(s['max_error_cm'], error)
        assert error < .001, error
        yawerror = (roots[0].rotation.rotator().yaw - a.get_actor_rotation().yaw + 180) % 360 - 180
        assert abs(yawerror) < .001, yawerror
        row = {'t': unreal.GameplayStatics.get_time_seconds(w), 'root': xyz(p),
            'raw': xyz(raw[1].translation), 'future1': xyz(roots[1].translation)}
        if s['rows']:
            prev = s['rows'][-1]
            if prev['raw'] == row['raw'] and sum((x-y)**2 for x,y in zip(prev['root'],row['root'])) > .000001:
                s['subframe_advances'] += 1
        s['rows'].append(row)
        if len(s['rows']) >= 100:
            assert s['subframe_advances'] > 0, 'No moving between-policy frames observed in this setup'
            finish('passed')
    except Exception: finish('failed', traceback.format_exc())
s['cb'] = unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()
