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


@pytest.mark.parametrize('subtype,rate', [('PCM_16',44100),('PCM_24',48000),('FLOAT',96000)])
def test_default_is_sample_exact_and_preserves_format(tmp_path,subtype,rate):
    path=tmp_path/'neutral.wav'
    samples=np.random.default_rng(3).uniform(-.97,.97,(rate//10,2)).astype(np.float32)
    sf.write(path,samples,rate,subtype=subtype)
    audio=load_audio(path)
    result=render(audio,Settings())
    assert result[1]==rate and np.array_equal(result[0],audio.samples)
    output=save_render(audio,Settings(),result,tmp_path,'neutral copy')
    actual,out_rate=sf.read(output,dtype='float32',always_2d=True)
    assert out_rate==rate and sf.info(output).subtype==subtype
    assert np.array_equal(actual,audio.samples)


def test_playback_analysis_follows_local_frequency_and_waveform():
    from visual_audio import playback_analysis
    rate=48000
    t=np.arange(rate*4)/rate
    signal=np.where(t<2,.1*np.sin(2*np.pi*220*t),.03*np.sin(2*np.pi*3000*t))[:,None].astype(np.float32)
    early=playback_analysis(signal,rate,rate)
    late=playback_analysis(signal,rate,rate*3)
    assert abs(early['frequencies'][early['spectrum'].argmax()]-220)<15
    assert abs(late['frequencies'][late['spectrum'].argmax()]-3000)<60
    assert late['view_start']>early['view_start']
    assert late['peak']<early['peak']/2
    assert not np.array_equal(early['peaks'],late['peaks'])


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


@pytest.mark.parametrize('channels',[1,2])
def test_compression_reduces_dynamic_range_and_links_channels(channels):
    from audio_engine import apply_compression
    rate=48000
    t=np.arange(rate*2)/rate
    mono=np.where(t<1,.02,.5)*np.sin(2*np.pi*440*t)
    samples=np.stack([mono,-.25*mono],axis=1)[:,:channels].astype(np.float32)
    untouched=samples.copy()
    assert Settings().compression==0
    assert apply_compression(samples,rate,0) is samples
    contrasts=[]
    for amount in (0,.25,.5,1):
        output=apply_compression(samples,rate,amount)
        quiet=np.sqrt(np.mean(output[rate//2:rate,0]**2))
        loud=np.sqrt(np.mean(output[rate*3//2:,0]**2))
        contrasts.append(loud/quiet)
        assert output.shape==samples.shape and np.isfinite(output).all()
        assert np.all(np.abs(output)<=np.abs(samples))
        if channels==2:
            assert np.array_equal(output[:,1],-.25*output[:,0])
        # A quiet recording gets the same relative compression, without a boost.
        softer=apply_compression(samples*.01,rate,amount)
        assert np.allclose(softer,output*.01,atol=1e-8,rtol=1e-5)
    assert all(a>b for a,b in zip(contrasts,contrasts[1:]))
    assert contrasts[-1]<contrasts[0]/4
    assert np.array_equal(samples,untouched)
    for length in (1,48):
        silence=np.zeros((length,channels),dtype=np.float32)
        assert np.array_equal(apply_compression(silence,rate,1),silence)
        short=np.ones((length,channels),dtype=np.float32)*.2
        result=apply_compression(short,rate,1)
        assert result.shape==short.shape and np.isfinite(result).all()


def test_compression_cache_export_and_validation(source,tmp_path,monkeypatch):
    import audio_engine as engine
    settings=plain(pitch=2,eq=(0,0,-4,0,0),reverb=.1,polish=.2)
    cache=engine.RenderCache()
    dry=render(source,settings,cache=cache)
    def unexpected(*args,**kwargs):
        pytest.fail('Compression edits must reuse the cached upstream effects.')
    with monkeypatch.context() as changes:
        changes.setattr(engine,'apply_tone_eq',unexpected)
        changes.setattr(engine,'time_stretch',unexpected)
        changes.setattr(engine,'Pedalboard',unexpected)
        render(source,replace(settings,compression=.3),cache=cache)
        edited=replace(settings,compression=.7)
        compressed=render(source,edited,cache=cache)
        bypassed=render(source,settings,cache=cache)
    reference=render(source,edited)
    assert np.array_equal(reference[0],compressed[0]) and reference[2]==compressed[2]
    assert np.array_equal(bypassed[0],dry[0]) and bypassed[2]==dry[2]
    assert np.mean(compressed[0]**2)<np.mean(dry[0]**2)
    output=save_render(source,edited,compressed,tmp_path,'compressed')
    saved,rate=sf.read(output,dtype='float32',always_2d=True)
    assert rate==compressed[1] and np.array_equal(saved,compressed[0])
    recipe=json.loads(output.with_suffix('.recipe.json').read_text(encoding='utf-8'))
    assert recipe['settings']['compression']==.7
    for invalid in (-.01,1.01,float('nan')):
        with pytest.raises(ValueError):
            render(source,replace(settings,compression=invalid))


def test_eq_denoise_resample_channels(source):
    x, rate, _ = render(source, plain(eq=(0,0,9,0,0), highpass=60,denoise=3,noise_floor=-65,sample_rate=44100,channels='Mono'))
    assert rate == 44100 and x.shape[1] == 1 and np.isfinite(x).all()
    assert abs(len(x)/rate-source.duration) < .03
    y, _, _ = render(source, plain(eq=(0,0,-9,0,0)))
    z, _, _ = render(source, plain(eq=(0,0,9,0,0)))
    assert np.sqrt(np.mean(z*z)) > np.sqrt(np.mean(y*y))*1.4


def test_mouse_targetable_eq_matches_rendered_frequency_response(source):
    from visual_audio import eq_response
    settings=plain(eq=(-12,0,0,0,0),eq_frequencies=(440,250,1000,4000,12000),eq_q=(4,.85,.85,.85,.85))
    result,rate,_=render(source,settings)
    amplitude=np.sqrt(np.mean(result[4800:-4800,0]**2))/np.sqrt(np.mean(source.samples[4800:-4800,0]**2))
    measured=20*np.log10(amplitude)
    displayed=eq_response(settings,rate,np.array([440.]))[0]
    assert abs(measured+12)<.1
    assert abs(measured-displayed)<.1


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
    settings = replace(Settings(), subtype=subtype,gain_db=18,protect=True,sample_rate=48000)
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


def test_qt_end_to_end(source,tmp_path,monkeypatch):
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
        window.protect.setChecked(True)
        window.controls['gain_db'].set_value(18)
        settle()
        protected=window.wave.processed['peak']
        window.protect.setChecked(False)
        settle()
        assert window.wave.processed['peak'] > protected*1.5
        assert window.result[2]['export_blocked']
        window.protect.setChecked(True)
        settle()
        assert window.wave.processed['peak'] < .9
        assert not window.result[2]['export_blocked']
        window.controls['gain_db'].set_value(0)
        settle()
        # A late result from an older slider position must never replace the newest edit.
        import app as app_module
        actual_render=app_module.render
        def slow_render(audio,settings,cancel=None,progress=lambda text:None,**kwargs):
            time.sleep(.2)
            return actual_render(audio,settings,None,progress,**kwargs)
        with monkeypatch.context() as changes:
            changes.setattr(app_module,'render',slow_render)
            window.controls['gain_db'].set_value(4)
            QTest.qWait(260)
            window.controls['gain_db'].set_value(-6)
            settle()
            assert window.result_settings.gain_db == -6
            assert abs(window.wave.processed['peak']-.2*10**(-6/20)) < .0001
        window.controls['gain_db'].set_value(0)
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
        window.controls['compression'].set_value(60)
        window.wave_trim(.125,1.5)
        window.output_name.setFocus()
        window.output_name.selectAll()
        window.output_name.setText('Game impact ')
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
        assert settings.reverb==0 and settings.polish==0 and settings.start==0 and settings.compression==0
        assert window.controls['compression'].spin.text()=='Off'
        assert settings.subtype=='SOURCE' and not settings.protect and not settings.normalize
        assert settings.fade_in_ms == settings.fade_out_ms == 0
        assert settings.sample_rate == 0 and window.loop.isChecked()
        assert window.wave.zoom == 64 and window.player.volume == 1
        assert settings.end==window.audio.duration
        assert window.output_name.text() == 'Game impact é_mix'
        # A second generate from a saved WAV is a real remix, without replacing either input.
        window.output_name.setText('Game impact é')
        window.generate()
        settle()
        assert (target/'Game impact é_002.wav').exists()
        assert not errors, errors
        # Exercise playback on the real Windows output device at zero monitor gain.
        window.player.volume=0
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


def test_transport_focus_live_edits_and_loop(source,tmp_path):
    from PySide6.QtCore import Qt,QEvent,QPoint
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QWidget,QToolTip
    from app import Studio
    app=QApplication.instance() or QApplication([])
    window=Studio(tmp_path/'transport-state',source.path.parent,tmp_path/'out')
    errors=[]
    window.show_error=errors.append
    window.show()
    def settle():
        deadline=time.monotonic()+20
        while window.busy or window.live_worker or window.live_timer.isActive():
            app.processEvents();time.sleep(.01)
            assert time.monotonic()<deadline
    try:
        window.source.list.setCurrentRow(0);settle()
        assert window.loop.isChecked() and window.player.loop
        assert window.player.volume==1 and window.wave.zoom==64
        assert not hasattr(window,'monitor') and not hasattr(window,'zoom')
        assert all(not widget.toolTip() for widget in window.findChildren(QWidget))
        # Even elided list items must not create implicit Qt tooltips.
        QApplication.sendEvent(window.source.list.viewport(),QHelpEvent(QEvent.Type.ToolTip,QPoint(20,20),QPoint(20,20)))
        QTest.qWait(30)
        assert not QToolTip.isVisible()
        window.player.volume=0  # Exercise the actual device without making test noise.
        window.preview();QTest.qWait(180)
        assert window.player.stream is not None and window.wave.playback is not None
        window.toggle_play()
        assert window.player.paused and not window.timer.isActive()
        # These keys win even after text fields, sliders, lists, combo boxes and buttons have focus.
        for control in [window.eq_sliders[2],window.pitch_spin.lineEdit(),window.output_name,
                        window.source.list,window.rate,window.normalize,window.generate_button]:
            control.setFocus()
            window.player.seek(.5)
            settings=window.current_settings();name=window.output_name.text();selected=window.source.list.currentRow()
            QTest.keyClick(control,Qt.Key.Key_Right)
            assert abs(window.player.position()-.75)<1/window.player.rate
            QTest.keyClick(control,Qt.Key.Key_Left)
            assert abs(window.player.position()-.5)<1/window.player.rate
            QTest.keyClick(control,Qt.Key.Key_Space)
            assert not window.player.paused and window.player.stream is not None
            QTest.qWait(30)
            QTest.keyClick(control,Qt.Key.Key_Space)
            assert window.player.paused and window.player.stream is None
            position=window.player.position();QTest.qWait(50)
            assert window.player.position()==position
            assert window.current_settings()==settings and window.output_name.text()==name
            assert window.source.list.currentRow()==selected and not window.busy
        window.details.show()
        control=window.controls['fade_in_ms'].spin.lineEdit();control.setFocus()
        window.player.seek(.5);QTest.keyClick(control,Qt.Key.Key_Right)
        assert abs(window.player.position()-.75)<1/window.player.rate
        window.details.hide()
        window.toggle_play()
        stream=window.player.stream
        # All changes use the same running stream, including sample-rate and channel changes.
        window.eq_freqs[2].setValue(440);window.eq_spins[2].setValue(-10)
        assert window.player.stream is stream and not window.player.paused
        settle();QTest.qWait(250)
        assert window.player.stream is stream and not window.player.paused
        assert window.result_settings.eq[2]==-10
        assert window.player.samples is window.result[0]
        assert window.wave.playback is not None and window.wave.cursor is not None
        window.rate.setCurrentIndex(window.rate.findData(44100));window.channel_mode.setCurrentText('Mono')
        settle();QTest.qWait(200)
        assert window.player.stream is stream and not window.player.paused
        assert window.player.samples.shape[1]==1 and window.player.rate==48000
        # Paused edits update the buffer but never resume or reset the position.
        window.toggle_play();position=window.player.position()
        window.controls['gain_db'].set_value(-3);settle()
        assert window.player.paused and abs(window.player.position()-position)<1/44100
        window.player.seek(0);window.seek_relative(-.25)
        assert window.player.position()==0
        window.player.seek(.4);window.toggle_play();QTest.qWait(2300)
        assert window.player.stream is not None and not window.player.finished
        assert len(window.player.samples)/window.player.rate==pytest.approx(2,abs=.0001)
        window.loop.setChecked(False)
        window.player.seek(1.9);QTest.qWait(700)
        assert window.player.stream is None and not window.timer.isActive()
        assert not errors,errors
    finally:
        window.close()
        deadline=time.monotonic()+5
        while (window.busy or window.live_worker) and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        app.processEvents()


@pytest.mark.parametrize('index,cutoff,stop,passed',[(0,200,50,1000),(4,4000,10000,1000)])
def test_outer_eq_stays_cut_and_matches_audio(tmp_path,index,cutoff,stop,passed):
    from audio_engine import edge_eq_response,EQ_CUT
    from visual_audio import eq_response
    rate=48000
    t=np.arange(4*rate)/rate
    samples=(.1*np.sin(2*np.pi*stop*t)+.1*np.sin(2*np.pi*passed*t))[:,None].astype(np.float32)
    path=tmp_path/'two tones.wav';sf.write(path,samples,rate,subtype='FLOAT')
    source=load_audio(path)
    freqs=list(Settings().eq_frequencies);freqs[index]=cutoff
    for gain in [-12.,EQ_CUT]:
        gains=[0]*5;gains[index]=gain
        settings=plain(eq=tuple(gains),eq_frequencies=tuple(freqs))
        grid=np.geomspace(1,rate/2,3000)
        response=edge_eq_response(settings,rate,grid)
        blocked=grid<=cutoff if index==0 else grid>=cutoff
        expected=0 if gain==EQ_CUT else 10**(gain/20)
        assert np.allclose(response[blocked],expected,atol=1e-12)
        assert np.all(np.diff(response)>=-1e-12) if index==0 else np.all(np.diff(response)<=1e-12)
        result,_,_=render(source,settings)
        middle=result[rate:3*rate,0]
        times=t[rate:3*rate]
        measured=abs(2*np.mean(middle*np.exp(-2j*np.pi*stop*times)))/.1
        kept=abs(2*np.mean(middle*np.exp(-2j*np.pi*passed*times)))/.1
        assert abs(measured-expected)<.0001
        assert abs(kept-1)<.0001
        displayed=eq_response(settings,rate,np.array([stop,passed]))
        assert displayed[0]<-100 if gain==EQ_CUT else abs(displayed[0]-gain)<1e-8
        assert abs(displayed[1])<1e-8
        assert len(result)==len(samples) and np.isfinite(result).all()


def test_both_outer_cuts_can_reach_zero(source):
    from audio_engine import EQ_CUT
    settings=plain(eq=(EQ_CUT,0,0,0,EQ_CUT),eq_frequencies=(20000,250,1000,4000,20))
    result,_,_=render(source,settings)
    assert np.count_nonzero(result)==0


@pytest.mark.parametrize('index,centre,passed',[(1,250,8000),(2,1000,10000),(3,4000,80)])
def test_middle_eq_deep_cut_matches_audio_and_graph(tmp_path,index,centre,passed):
    from audio_engine import EQ_CUT,peaking_sos
    from scipy.signal import freqz
    from visual_audio import eq_response
    rate=48000
    t=np.arange(4*rate)/rate
    samples=(.1*np.sin(2*np.pi*centre*t)+.1*np.sin(2*np.pi*passed*t))[:,None].astype(np.float32)
    path=tmp_path/'middle tones.wav';sf.write(path,samples,rate,subtype='FLOAT')
    source=load_audio(path)
    for gain in (-24,EQ_CUT+.1,EQ_CUT):
        gains=[0]*5;gains[index]=gain
        settings=plain(eq=tuple(gains))
        result,_,_=render(source,settings)
        assert np.isfinite(result).all() and result.shape==samples.shape
        displayed=eq_response(settings,rate,np.array([centre,passed]))
        expected=10**(displayed/20)
        for frequency,amplitude in zip((centre,passed),expected):
            measured=abs(2*np.mean(result[rate:3*rate,0]*np.exp(-2j*np.pi*frequency*t[rate:3*rate])))/.1
            assert abs(measured-amplitude)<2e-6
        assert expected[1]>.1
        if gain==EQ_CUT:
            assert displayed[0]<-150
        else:
            assert abs(displayed[0]-gain)<1e-7
    # The final step must not suddenly widen/narrow the cut or boost other bins.
    grid=np.geomspace(1,rate/2,4000)
    responses=[]
    for gain in (EQ_CUT+.1,EQ_CUT):
        sos=peaking_sos(centre,gain,.85,rate)
        _,response=freqz(sos[:3],sos[3:],worN=2*np.pi*grid/rate)
        responses.append(response)
        assert np.max(np.abs(np.roots(sos[3:])))<1
    assert np.max(np.abs(responses[0]-responses[1]))<.001


def test_all_eq_sliders_reach_cut_and_reset(source,tmp_path):
    from PySide6.QtCore import Qt,QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QStyle,QStyleOptionSlider
    from app import Studio
    from audio_engine import EQ_CUT
    app=QApplication.instance() or QApplication([])
    window=Studio(tmp_path/'eq-state',source.path.parent,tmp_path/'out')
    window.show()
    errors=[];window.show_error=errors.append
    def settle():
        deadline=time.monotonic()+20
        while window.busy or window.live_worker or window.live_timer.isActive():
            app.processEvents();time.sleep(.001)
            assert time.monotonic()<deadline
    try:
        window.load(source.path);settle()
        for index,slider in enumerate(window.eq_sliders):
            option=QStyleOptionSlider();slider.initStyleOption(option)
            handle=slider.style().subControlRect(QStyle.ComplexControl.CC_Slider,option,
                                                QStyle.SubControl.SC_SliderHandle,slider).center()
            QTest.mousePress(slider,Qt.MouseButton.LeftButton,pos=handle)
            QTest.mouseMove(slider,QPoint(0,handle.y()))
            QTest.mouseRelease(slider,Qt.MouseButton.LeftButton,pos=QPoint(0,handle.y()))
            assert window.eq_spins[index].value()==EQ_CUT
            assert window.eq_spins[index].text()=='CUT'
            assert window.wave.settings.eq[index]==EQ_CUT
            settle()
            assert window.result_settings.eq[index]==EQ_CUT
            QTest.mouseDClick(slider,Qt.MouseButton.LeftButton)
            assert window.eq_spins[index].value()==0
            assert window.wave.settings.eq[index]==0
        settle()
        assert np.array_equal(window.result[0],source.samples)
        assert not errors,errors
    finally:
        window.close();settle();app.processEvents()


def test_all_eq_mouse_reaches_cut_and_exact_neutral():
    from PySide6.QtCore import Qt,QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from visual_audio import AudioDisplay
    from audio_engine import EQ_CUT
    app=QApplication.instance() or QApplication([])
    wave=AudioDisplay();wave.resize(1100,500);wave.show()
    changes=[]
    def changed(i,f,g,q):
        changes.append((i,f,g,q))
        gains=list(wave.settings.eq);gains[i]=g
        wave.settings=replace(wave.settings,eq=tuple(gains))
    wave.bandChanged.connect(changed)
    try:
        rect,_,_=wave.geometry_parts()
        for i in range(5):
            x=round(wave.frequency_x(wave.settings.eq_frequencies[i]))
            QTest.mousePress(wave,Qt.MouseButton.LeftButton,pos=QPoint(x,round(wave.gain_y(0))))
            QTest.mouseMove(wave,QPoint(x,round(rect.bottom()-2)))
            QTest.mouseRelease(wave,Qt.MouseButton.LeftButton,pos=QPoint(x,round(rect.bottom()-2)))
            assert changes[-1][0]==i and changes[-1][2]==EQ_CUT
            QTest.mousePress(wave,Qt.MouseButton.LeftButton,pos=QPoint(x,round(rect.bottom()-2)))
            QTest.mouseMove(wave,QPoint(x,round(wave.gain_y(0))))
            QTest.mouseRelease(wave,Qt.MouseButton.LeftButton,pos=QPoint(x,round(wave.gain_y(0))))
            assert changes[-1][0]==i and changes[-1][2]==0
    finally:
        wave.close();app.processEvents()


def test_refresh_restores_edit_after_pending_render(source,tmp_path):
    from PySide6.QtWidgets import QApplication
    from app import Studio
    from audio_engine import EQ_CUT
    app=QApplication.instance() or QApplication([])
    window=Studio(tmp_path/'refresh-state',source.path.parent,tmp_path/'out')
    window.show()
    def settle(w):
        deadline=time.monotonic()+20
        while w.busy or w.live_worker or w.live_timer.isActive():
            app.processEvents();time.sleep(.01)
            assert time.monotonic()<deadline
        app.processEvents()
    try:
        window.load(source.path);settle(window)
        window.pitch_spin.setValue(2)
        window.eq_spins[0].setValue(EQ_CUT)
        window.eq_freqs[0].setValue(150)
        window.controls['fade_in_ms'].set_value(17)
        window.controls['gain_db'].set_value(-4)
        window.controls['compression'].set_value(57)
        window.loop.setChecked(False)
        window.output_name.setText('Saved edit name')
        expected=window.current_settings()
        # Refresh immediately, with the live render still queued.
        window.refresh_app_button.click()
        settle(window)
        assert not window.isVisible() and window.restart_session.is_file()
        snapshot=json.loads(window.restart_session.read_text(encoding='utf-8'))
        restored=Studio(tmp_path/'restored-state',snapshot['source'],snapshot['target'])
        restored.show()
        try:
            restored.load(Path(snapshot['audio']),snapshot);settle(restored)
            assert restored.current_settings()==expected
            assert restored.output_name.text()=='Saved edit name'
            assert not restored.loop.isChecked()
            assert restored.audio.path==source.path
            assert restored.result_settings==expected
            assert restored.player.stream is None
        finally:
            restored.close();settle(restored)
    finally:
        window.close();app.processEvents()


def test_single_play_button_original_bypasses_without_losing_edit(source,tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app import Studio
    app=QApplication.instance() or QApplication([])
    window=Studio(tmp_path/'bypass-state',source.path.parent,tmp_path/'out')
    window.show()
    errors=[];window.show_error=errors.append
    def settle():
        deadline=time.monotonic()+20
        while window.busy or window.live_worker or window.live_timer.isActive():
            app.processEvents();time.sleep(.01)
            assert time.monotonic()<deadline
        app.processEvents()
    try:
        window.load(source.path);settle()
        assert not hasattr(window,'original_button') and not hasattr(window,'preview_button')
        assert window.play_button.text()=='▶  Play' and not window.play_original_check.isChecked()
        window.controls['gain_db'].set_value(-9)
        window.controls['compression'].set_value(70)
        window.controls['start'].set_value(.25)
        window.controls['end'].set_value(1.75)
        window.controls['speed'].set_value(125)
        settle();settings=window.current_settings()
        processed=window.result[0]
        assert len(processed)<len(source.samples)
        window.player.volume=0
        window.play_button.click();QTest.qWait(200)
        stream=window.player.stream
        assert window.play_mode=='processed' and window.play_button.text()=='Ⅱ  Pause'
        window.play_original_check.click();QTest.qWait(200)
        assert window.player.stream is stream and window.play_mode=='original'
        assert np.array_equal(window.player.samples,source.samples)
        assert window.current_settings()==settings
        assert window.wave.playback['duration']==source.duration
        # Editing during bypass must never leak the processed buffer into playback.
        window.controls['gain_db'].set_value(-12);settle();QTest.qWait(100)
        assert window.play_mode=='original' and np.array_equal(window.player.samples,source.samples)
        window.play_original_check.click();QTest.qWait(200)
        assert window.player.stream is stream and window.play_mode=='processed'
        assert window.player.samples is window.result[0]
        # Space still wins over a focused checkbox; it pauses instead of toggling bypass.
        window.play_original_check.setFocus()
        QTest.keyClick(window.play_original_check,Qt.Key.Key_Space)
        assert window.player.paused and not window.play_original_check.isChecked()
        window.player.seek(.4)
        window.play_original_check.click()
        assert window.player.paused and abs(window.player.position()-.4)<1/source.rate
        assert np.array_equal(window.player.samples,source.samples)
        window.play_original_check.click()
        assert window.player.paused and abs(window.player.position()-.4)<1/source.rate
        assert window.player.samples is window.result[0]
        window.stop();window.play_original_check.click()
        assert window.wave.original_view and window.player.samples is None
        window.play_button.click();QTest.qWait(100)
        assert window.play_mode=='original' and np.array_equal(window.player.samples,source.samples)
        window.stop()
        window.reset_controls();settle()
        assert not window.play_original_check.isChecked()
        assert not errors,errors
    finally:
        window.close();app.processEvents()


@pytest.mark.parametrize('rate',[8000,48000,96000])
def test_in_process_tone_filters_match_previous_ffmpeg(tmp_path,rate):
    from audio_engine import apply_tone_eq,ffmpeg_filter
    samples=np.random.default_rng(29).uniform(-.1,.1,(rate,2)).astype(np.float32)
    settings=plain(eq=(0,8,-11,5,0),eq_frequencies=(80,150,900,3000,12000),eq_q=(.85,.3,4,1.5,.85),highpass=80)
    filters=['highpass=f=80:poles=2']
    filters += [f'equalizer=f={min(f,rate*.45)}:t=q:w={q}:g={g}' for f,g,q in zip(settings.eq_frequencies[1:4],settings.eq[1:4],settings.eq_q[1:4])]
    previous,_=ffmpeg_filter(samples,rate,filters)
    reference,_=ffmpeg_filter(samples,rate,[f+':precision=f64' for f in filters])
    optimized=apply_tone_eq(samples,rate,settings)
    # The same coefficients in float64 match the high-precision reference.
    # The old auto/float32 filter state accumulated small low-frequency errors.
    assert np.max(np.abs(reference-optimized))<2e-8
    assert np.sqrt(np.mean((previous-optimized)**2))<3e-5


def test_cached_edits_match_uncached_and_reuse_pitch(source,monkeypatch):
    import audio_engine as engine
    cache=engine.RenderCache()
    actual_stretch=engine.time_stretch
    calls=[]
    def counted(*args,**kwargs):
        calls.append(kwargs)
        return actual_stretch(*args,**kwargs)
    monkeypatch.setattr(engine,'time_stretch',counted)
    settings=plain(pitch=3,denoise=2,reverb=.1,fade_in_ms=8,polish=.2)
    render(source,settings,cache=cache)
    count=len(calls)
    edited=replace(settings,eq=(-6,3,-5,2,-9),highpass=45)
    cached=render(source,edited,cache=cache)
    assert len(calls)==count
    reference=render(source,edited)
    assert np.array_equal(cached[0],reference[0]) and cached[2]==reference[2]
    changed=replace(edited,gain_db=-5,normalize=True,protect=True,subtype='PCM_16')
    cached=render(source,changed,cache=cache)
    reference=render(source,changed)
    assert np.array_equal(cached[0],reference[0]) and cached[2]==reference[2]
    changed=replace(changed,pitch=5)
    before=len(calls);render(source,changed,cache=cache)
    assert len(calls)==before+1
    # Identity changes and bounded storage cannot return another clip's audio.
    other=replace(source,samples=source.samples*.2)
    other_result=render(other,Settings(),cache=cache)
    assert np.array_equal(other_result[0],other.samples)
    small=engine.RenderCache(max_bytes=source.samples.nbytes+16)
    render(source,settings,cache=small)
    assert small.bytes<=small.max_bytes


@pytest.mark.parametrize('effect',['eq','compression'])
def test_preview_updates_during_drag_and_curve_never_rolls_back(source,tmp_path,monkeypatch,effect):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    import app as module
    app=QApplication.instance() or QApplication([])
    w=module.Studio(tmp_path/'drag-state',source.path.parent,tmp_path/'out')
    w.show();errors=[];w.show_error=errors.append
    def settle():
        deadline=time.monotonic()+20
        while w.busy or w.live_worker or w.live_timer.isActive():
            app.processEvents();time.sleep(.001)
            assert time.monotonic()<deadline
    try:
        w.load(source.path);settle()
        w.player.volume=0;w.preview();QTest.qWait(120)
        stream=w.player.stream
        actual_render=module.render
        delivered=[]
        value=lambda settings: settings.eq[2] if effect=='eq' else settings.compression
        original_accept=w.accept_result
        def accepted(result,settings,*args,**kwargs):
            delivered.append(value(settings))
            return original_accept(result,settings,*args,**kwargs)
        w.accept_result=accepted
        def delayed(audio,settings,*args,**kwargs):
            time.sleep(.045)
            return actual_render(audio,settings,*args,**kwargs)
        monkeypatch.setattr(module,'render',delayed)
        # Continuous slider-down events; previews must arrive before release.
        slider=w.eq_sliders[2] if effect=='eq' else w.controls['compression'].slider
        slider.setSliderDown(True)
        for i in range(24):
            setting=-10-i if effect=='eq' else 25+3*i
            expected=setting/(10 if effect=='eq' else 100)
            slider.setValue(setting)
            assert value(w.wave.settings)==expected
            QTest.qWait(20)
            assert value(w.wave.settings)==expected
        assert len(delivered)>=2,delivered
        slider.setSliderDown(False);settle();QTest.qWait(160)
        assert value(w.result_settings)==expected and value(w.wave.settings)==expected
        assert w.player.stream is stream and not w.player.paused
        assert w.player.samples is w.result[0]
        if effect=='compression':
            assert np.mean(w.wave.processed['peaks']**2)<np.mean(w.wave.source['peaks']**2)/2
            w.player.pause();w.player.seek(.4)
            position=w.player.position()
            slider.setValue(50);settle()
            assert w.player.paused and abs(w.player.position()-position)<1/source.rate
            QTest.mouseDClick(slider,Qt.MouseButton.LeftButton);settle()
            assert w.current_settings().compression==0
            assert np.array_equal(w.result[0],source.samples)
        assert not errors,errors
    finally:
        w.close()
        deadline=time.monotonic()+5
        while (w.busy or w.live_worker) and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        app.processEvents()
