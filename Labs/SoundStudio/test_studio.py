"""Signal-level and real Qt workflow verification; all outputs go to temporary folders."""
from dataclasses import replace
from pathlib import Path
import ctypes
import json
import os
import threading
import time

import numpy as np
import pytest
import soundfile as sf

from audio_engine import Settings, load_audio, render, save_render, file_hash, output_stem, Cancelled, APP_ID


@pytest.fixture
def source(tmp_path):
    rate = 48000
    t = np.arange(rate*2)/rate
    data = np.stack([.2*np.sin(2*np.pi*440*t), .1*np.sin(2*np.pi*880*t)], axis=1)
    path = tmp_path/'Source é & test.wav'
    sf.write(path, data, rate, subtype='PCM_24')
    return load_audio(path)


def plain(**values):
    return replace(Settings(fade_in_ms=0, fade_out_ms=0, protect=False, subtype='FLOAT', sample_rate=0), **values)


def dominant(data, rate):
    middle = data[len(data)//4:len(data)*3//4, 0]
    spectrum = np.abs(np.fft.rfft(middle*np.hanning(len(middle))))
    return np.argmax(spectrum)*rate/len(middle)


def test_neutral_and_trim_exact(source):
    x, rate, _ = render(source, plain())
    assert np.array_equal(x, source.samples)
    x, _, _ = render(source, plain(start=.25, end=1.25))
    assert np.array_equal(x, source.samples[12000:60000])


@pytest.mark.parametrize('pitch,speed,frequency,duration', [(12,1,880,2),(-12,1,220,2),(0,2,440,1),(3,.75,440*2**.25,2/.75)])
def test_pitch_and_speed_are_independent(source,pitch,speed,frequency,duration):
    x, rate, _ = render(source, plain(pitch=pitch,speed=speed))
    assert abs(len(x)/rate-duration) <= 1/rate
    assert abs(dominant(x,rate)-frequency) < 4
    assert x.shape[1] == 2


def test_fades_reverb_and_polish(source):
    dry, _, _ = render(source, plain(fade_in_ms=20, fade_out_ms=40))
    assert np.all(dry[0] == 0) and np.all(dry[-1] == 0)
    wet, rate, metrics = render(source, plain(reverb=.2,room=.5,polish=.5))
    assert len(wet) > len(source.samples)
    assert np.max(np.abs(wet[len(source.samples):])) > .0001
    assert np.isfinite(wet).all() and metrics['notes']


def test_eq_denoise_resample_channels(source):
    x, rate, _ = render(source, plain(eq=(0,0,9,0,0), highpass=60,denoise=3,noise_floor=-65,sample_rate=44100,channels='Mono'))
    assert rate == 44100 and x.shape[1] == 1 and np.isfinite(x).all()
    assert abs(len(x)/rate-source.duration) < .03
    y, _, _ = render(source, plain(eq=(0,0,-9,0,0)))
    z, _, _ = render(source, plain(eq=(0,0,9,0,0)))
    assert np.sqrt(np.mean(z*z)) > np.sqrt(np.mean(y*y))*1.4


@pytest.mark.parametrize('rate,length', [(8000,80),(44100,4410),(48000,48),(48000,4800),(96000,9600)])
def test_denoise_preserves_transient_timing_and_flushes_end(tmp_path,rate,length):
    path=tmp_path/'transient.wav'
    data=np.zeros((length,1),np.float32)
    index=length-5
    data[index]=.5
    sf.write(path,data,rate,subtype='FLOAT')
    audio=load_audio(path)
    x,out_rate,_=render(audio,plain(denoise=3))
    assert out_rate==rate and len(x)==length
    assert abs(int(np.argmax(np.abs(x[:,0])))-index)<=1
    assert np.max(np.abs(x)) > .25


@pytest.mark.parametrize('subtype,bits', [('PCM_16',16),('PCM_24',24),('FLOAT',32)])
def test_export_formats_dither_protection_recipe_and_no_overwrite(source,tmp_path,subtype,bits):
    settings = replace(Settings(), subtype=subtype,gain_db=18)
    result = render(source, settings)
    assert result[2]['estimated_true_peak_dbtp'] <= -1.0
    assert result[2]['protection_gain_db'] < 0
    original = file_hash(source.path)
    destination = save_render(source,settings,result,tmp_path,'Sword impact')
    second = save_render(source,settings,result,tmp_path,'Sword impact.wav')
    assert destination.name == 'Sword impact.wav' and second.name == 'Sword impact_002.wav'
    actual, rate = sf.read(destination,dtype='float32',always_2d=True)
    assert sf.info(destination).subtype == subtype
    assert rate == 48000 and np.array_equal(actual,result[0])
    assert file_hash(source.path) == original
    recipe = json.loads(destination.with_suffix('.recipe.json').read_text(encoding='utf-8'))
    assert recipe['source_sha256'] == original and recipe['output_sha256'] == file_hash(destination)
    reloaded = load_audio(destination)
    remixed = save_render(reloaded,Settings(),render(reloaded,Settings()),tmp_path,'Sword impact')
    assert remixed.name == 'Sword impact_003.wav'


def test_no_source_overwrite_and_changed_source_rejected(source,tmp_path):
    result = render(source,Settings())
    digest = file_hash(source.path)
    exported = save_render(source,Settings(),result,tmp_path,source.path.stem)
    assert exported != source.path and file_hash(source.path) == digest
    sf.write(source.path,np.zeros((4800,1)),48000)
    with pytest.raises(ValueError,match='changed'):
        save_render(source,Settings(),result,tmp_path,'should not exist')
    assert not (tmp_path/'should not exist.wav').exists()


@pytest.mark.parametrize('name',['../escape','bad/name','bad\\name','CON','LPT1.wav','', 'a:b'])
def test_names_rejected(name):
    with pytest.raises(ValueError):
        output_stem(name)


def test_silence_short_clip_and_cancel(tmp_path):
    path = tmp_path/'tiny.wav'
    sf.write(path,np.zeros((48,1)),48000,subtype='PCM_16')
    audio = load_audio(path)
    x,rate,metrics = render(audio,replace(Settings(),normalize=True))
    assert len(x)==48 and np.isfinite(x).all()
    event = threading.Event()
    event.set()
    with pytest.raises(Cancelled):
        render(audio,Settings(),event)
    assert metrics['peak_dbfs'] < -85


def test_invalid_float_and_integer_clipping(source,tmp_path):
    with pytest.raises(ValueError,match='clip'):
        render(source,replace(Settings(),protect=False,gain_db=18))
    path = tmp_path/'invalid.wav'
    sf.write(path,np.array([[np.nan]],dtype=np.float32),48000,subtype='FLOAT')
    with pytest.raises(ValueError,match='invalid'):
        load_audio(path)


def test_qt_end_to_end(source,tmp_path):
    from PySide6.QtCore import Qt,QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app import Studio, STYLE
    if os.name == 'nt':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    target = tmp_path/'outputs'
    target.mkdir()
    window = Studio(tmp_path/'state',source.path.parent,target)
    window.show()

    def settle():
        deadline = time.monotonic()+25
        while (window.busy or window.live_worker or window.live_timer.isActive()) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        app.processEvents()
        assert not window.busy and window.live_worker is None

    # Show any GUI error as a test failure instead of blocking on a dialog.
    errors=[]
    window.show_error = errors.append
    try:
        item=window.source.list.item(0)
        window.source.list.setCurrentItem(item)
        settle()
        assert window.audio.path == source.path
        assert window.current_settings().end == source.duration
        assert window.controls['speed'].spin.lineEdit().width() > 35
        assert window.pitch_spin.lineEdit().width() > 35
        assert window.result is not None and window.wave.processed is not None
        before_peak=window.wave.processed['peak']
        window.normalize.setChecked(True)
        settle()
        assert window.wave.processed['peak'] > before_peak*2
        assert window.result_settings.normalize
        window.normalize.setChecked(False)
        # The graph's mouse path moves the nearest band and updates the actual render.
        graph=window.wave
        graph_rect,_,_=graph.geometry_parts()
        point=QPoint(round(graph.frequency_x(650)),round(graph.gain_y(-5)))
        QTest.mouseClick(graph,Qt.MouseButton.LeftButton,pos=point)
        settle()
        assert min(abs(f-650) for f in window.current_settings().eq_frequencies) < 10
        assert min(window.current_settings().eq) < -4
        window.pitch.setValue(35)
        window.controls['speed'].slider.setValue(120)
        window.eq_sliders[2].setValue(25)
        window.controls['reverb'].set_value(10)
        window.controls['polish'].set_value(25)
        window.wave_trim(.125,1.5)
        window.output_name.setFocus()
        window.output_name.selectAll()
        QTest.keyClicks(window.output_name,'Game impact ')
        window.output_name.insert('é')
        assert window.output_name.text() == 'Game impact é'
        assert window.current_settings().pitch == 3.5
        assert window.current_settings().speed == 1.2
        window.generate_button.click()
        settle()
        assert not errors, errors
        output = target/'Game impact é.wav'
        assert output.exists()
        assert window.target.list.count() == 1
        saved_item=window.target.list.item(0)
        rect=window.target.list.visualItemRect(saved_item)
        # Actual double-click signal path, not a direct call to load().
        QTest.mouseClick(window.target.list.viewport(),Qt.MouseButton.LeftButton,pos=rect.center())
        QTest.qWait(50)
        QTest.mouseDClick(window.target.list.viewport(),Qt.MouseButton.LeftButton,pos=rect.center())
        settle()
        assert window.audio.path == output
        settings=window.current_settings()
        assert settings.pitch==0 and settings.speed==1 and settings.eq==(0,0,0,0,0)
        assert settings.reverb==0 and settings.polish==0 and settings.start==0
        assert settings.subtype=='PCM_16' and settings.protect and not settings.normalize
        assert settings.end==window.audio.duration
        assert window.output_name.text() == 'Game impact é_mix'
        # A second generate from a saved WAV is a real remix, without replacing either input.
        window.output_name.setText('Game impact é')
        window.generate()
        settle()
        assert (target/'Game impact é_002.wav').exists()
        assert not errors, errors
        # Exercise playback on the real Windows output device at zero monitor gain.
        window.monitor.setValue(0)
        window.preview()
        settle()
        QTest.qWait(130)
        assert not errors, errors
        assert window.player.stream is not None
        window.stop()
        assert window.player.stream is None and not window.timer.isActive()
        window.record_identity()
        identity=json.loads((tmp_path/'state'/'app-identity.json').read_text(encoding='utf-8'))
        if os.name=='nt':
            assert identity['actual_process_app_id']==APP_ID
            assert identity['small_icon_handle'] and identity['large_icon_handle']
        receipt=Path(__file__).resolve().parents[2]/'Saved'/'Diagnostics'/'SoundStudio20261022'
        receipt.mkdir(parents=True,exist_ok=True)
        window.resize(1500,970)
        app.processEvents()
        window.grab().save(str(receipt/'studio-main.png'))
        window.graph_band_changed(2,1750,-6,1.4)
        settle()
        app.processEvents()
        window.grab().save(str(receipt/'studio-effects.png'))
        window.normalize.setChecked(True)
        settle()
        app.processEvents()
        window.grab().save(str(receipt/'studio-eq.png'))
        (receipt/'ui-verification.json').write_text(json.dumps({'workflow':'source select → controls → renamed WAV → double-click remix → reset → unique export',
            'playback':'real output device, muted', 'identity':identity,'errors':errors},indent=2),encoding='utf-8')
    finally:
        window.close()
        deadline=time.monotonic()+5
        while (window.busy or window.live_worker) and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        app.processEvents()
