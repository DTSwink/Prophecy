"""MetaSounds tab UI tests (offscreen Qt; engine rendered manually for determinism)."""
import json
import time

import numpy as np
import pytest
import soundfile as sf

from test_metasounds import noise, tone

SR = 48000


@pytest.fixture
def ui(tmp_path):
    from PySide6.QtWidgets import QApplication
    from meta_theme import STYLE
    from metasounds_app import MetaSoundsWindow
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    source = tmp_path / 'Sounds'
    source.mkdir()
    files = {name: tone(source / f'{name}.wav', freq) for name, freq in
             (('whoosh', 300), ('impact', 900), ('grass', 500), ('stone', 2500))}
    files['bed'] = noise(source / 'bed.wav', 2., 2)
    w = MetaSoundsWindow(tmp_path / 'state', tmp_path / 'home', [('Sounds', source)])
    meta = w.tab
    meta.audio_button.setChecked(False)       # render by hand instead of through a device
    w.resize(1400, 900)
    w.show()

    def settle(seconds=.05):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        meta.push_timer.stop()
        meta.push()
        meta.engine.clips.wait()
    settle()
    try:
        yield w, meta, files, settle, app
    finally:
        w.close()
        app.processEvents()


def event_named(meta, name):
    return next(e for e in meta.project.events if e.name == name)


def test_window_starts_without_tooltips_and_library_lists_sounds(ui):
    w, meta, files, settle, app = ui
    assert meta.active and not meta.engine.running and w.windowTitle() == 'Prophecy MetaSounds'
    from PySide6.QtWidgets import QWidget
    assert all(not widget.toolTip() for widget in meta.findChildren(QWidget))
    assert meta.library.count() == 5
    assert meta.project_path.parent.name == 'home'


def test_layers_from_library_play_from_pads(ui):
    w, meta, files, settle, app = ui
    punch = event_named(meta, 'Punch')
    meta.add_files(punch.layers[0], [files['whoosh']])
    meta.add_files(punch.layers[1], [files['impact']])
    settle(.2)
    assert punch.layers[0].files == [files['whoosh']]
    meta.pad_pressed(punch.id)
    out = meta.engine.render_seconds(.5)
    assert np.abs(out).max() > .05
    first = np.abs(out[:int(.05 * SR)]).max()
    assert first > 0
    assert meta.selected_pad == punch.id
    saved = json.loads(meta.project_path.read_text()) if meta.project_path.exists() else None
    meta.save()
    saved = json.loads(meta.project_path.read_text())
    assert any(files['whoosh'] in l['files'] for e in saved['events'] for l in e['layers'])


def test_walking_uses_zone_surfaces_and_keys_move_the_character(ui):
    w, meta, files, settle, app = ui
    steps = event_named(meta, 'Footsteps')
    for layer in steps.layers:
        layer.files = [files['stone'] if layer.name == 'Stone' else files['grass']]
        layer.pitch_random = layer.volume_random = 0
    meta.changed()
    settle(.2)
    village = next(z for z in meta.project.zones if z.name == 'Village')
    meta.map.move_listener(1500, 1500)
    meta.set_gait('Run')
    meta.engine.render_seconds(2.5)
    out = meta.engine.render_seconds(1.)
    from test_metasounds import energy_at
    assert meta.engine.surface == 'Stone' and energy_at(out, 2500) > 10 * energy_at(out, 500)
    meta.set_gait('Idle')

    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    meta.map.setFocus()
    w.activateWindow()
    settle(.05)
    start = list(meta.map.listener)
    meta.map.camera = 0.
    app.sendEvent(meta.map, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_W, Qt.KeyboardModifier.NoModifier, 'w'))
    settle(.4)
    app.sendEvent(meta.map, QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_W, Qt.KeyboardModifier.NoModifier, 'w'))
    settle(.05)
    if w.isActiveWindow():
        assert meta.map.listener[0] > start[0] + 20 and abs(meta.map.listener[1] - start[1]) < 1
        assert meta.engine.listener[0] == pytest.approx(meta.map.listener[0])
        assert not meta.engine.moving


def test_map_tools_create_zones_and_emitters(ui):
    w, meta, files, settle, app = ui
    zones = len(meta.project.zones)
    meta.set_mode('zone')
    meta.map.zoneDrawn.emit([[0, 0], [500, 0], [500, 500]])
    settle()
    zone = meta.project.zones[-1]
    assert len(meta.project.zones) == zones + 1 and meta.selection == ('zone', zone.id) and meta.map.mode == 'edit'
    meta.delete_selection()
    assert len(meta.project.zones) == zones
    fire = event_named(meta, 'Campfire')
    meta.selected_event = fire.id
    meta.map.emitterPlaced.emit(100, 200)
    emitter = meta.project.emitters[-1]
    assert emitter.event == fire.id and (emitter.x, emitter.y) == (100, 200)


def test_every_inspector_and_page_builds(ui):
    w, meta, files, settle, app = ui
    for event in meta.project.events:
        meta.show_inspector('event', event.id)
    for zone in meta.project.zones:
        meta.show_inspector('zone', zone.id)
    for emitter in meta.project.emitters:
        meta.show_inspector('emitter', emitter.id)
    att = meta.project.attenuations[0]
    from meta_model import DISTANCE_MODELS, SHAPES
    for shape in SHAPES:
        for model in DISTANCE_MODELS:
            att.shape, att.model = shape, model
            meta.build_attenuation_page()
    meta.build_mixer_page()
    meta.build_project_page()
    settle()


def test_parameter_rename_follows_mappings_and_layers(ui):
    w, meta, files, settle, app = ui
    punch = event_named(meta, 'Punch')
    meta.show_inspector('event', punch.id)
    from PySide6.QtWidgets import QLineEdit
    edit = next(e for e in meta.inspector_scroll.widget().findChildren(QLineEdit) if e.text() == 'Intensity')
    edit.setText('Force')
    edit.editingFinished.emit()
    assert punch.parameters[0].name == 'Force' and all(b.parameter == 'Force' for b in punch.bindings)


def test_export_writes_unreal_manifest(ui, tmp_path):
    w, meta, files, settle, app = ui
    punch = event_named(meta, 'Punch')
    meta.add_files(punch.layers[1], [files['impact'], files['whoosh']])
    bed = event_named(meta, 'Forest bed')
    meta.add_files(bed.layers[0], [files['bed']])
    from meta_export import export_unreal
    folder, report = export_unreal(meta.project, tmp_path / 'export', meta.engine.clips.info, 'test')
    manifest = json.loads((folder / 'unreal_manifest.json').read_text())
    assert report['waves'] == 3
    names = [wv['asset'] for wv in manifest['sound_waves']]
    assert 'SW_CMB_Punch_Impact_01' in names and 'SW_AMB_ForestBed_Forest_01' in names
    assert (folder / 'Sounds' / 'Combat' / 'Punch' / 'CMB_Punch_Impact_02.wav').is_file()
    source = next(s for s in manifest['metasound_sources'] if s['asset'] == 'MSS_Punch')
    assert 'UE.Source.OneShot' in source['interfaces'] and source['attenuation'] == 'ATT_Combat'
    assert source['inputs'][0]['name'] == 'Intensity' and source['layers'][1]['delay_s'] == pytest.approx(.06)
    att = next(a for a in manifest['attenuations'] if a['asset'] == 'ATT_Combat')
    assert att['settings']['DistanceAlgorithm'] == 'EAttenuationDistanceModel::NaturalSound'
    assert any(v['name'] == 'Tavern (interior)' and len(v['components']) == 3 for v in manifest['audio_gameplay_volumes'])
    assert manifest['control_bus_mixes'][0]['asset'] == 'CBM_Duck_Ambience_By_Combat'
    stereo_warning = [x for x in manifest['warnings'] if 'stereo' in x]
    assert not stereo_warning                     # the stereo bed is a 2D loop, which is fine
    assert (folder / 'README_UNREAL.md').is_file() and (folder / 'metasounds_project.json').is_file()


def test_project_reloads_after_restart(tmp_path):
    from PySide6.QtWidgets import QApplication
    from metasounds_app import MetaSoundsWindow
    app = QApplication.instance() or QApplication([])
    w = MetaSoundsWindow(tmp_path / 'state', tmp_path / 'home', [('Sounds', tmp_path)])
    w.tab.project.name = 'Saved world'
    w.tab.project.events[0].name = 'Renamed'
    w.tab.changed()
    w.close()
    app.processEvents()
    again = MetaSoundsWindow(tmp_path / 'state', tmp_path / 'other', [('Sounds', tmp_path)])
    try:
        assert again.tab.project.name == 'Saved world'          # remembered project path
        assert again.tab.project.events[0].name == 'Renamed'
    finally:
        again.close()
        app.processEvents()
