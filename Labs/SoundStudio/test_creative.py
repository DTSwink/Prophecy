"""Signal and Qt integration checks for creative editing. Temporary files only."""
from dataclasses import replace,asdict
from pathlib import Path
import json
import threading
import time
import numpy as np
import pytest
import soundfile as sf
from audio_engine import Settings,Audio,RenderCache,load_audio,render,save_render,file_hash,Cancelled
from creative_audio import (trim_duration,volume_envelope,pitch_envelope,granular_synthesis,
                            stitch_clips,variant_settings,rename_wav,_sinc_read)


@pytest.fixture
def clip(tmp_path):
    rate=24000;t=np.arange(rate)/rate
    samples=np.stack([.1*np.sin(2*np.pi*440*t),.05*np.sin(2*np.pi*880*t)],axis=1).astype(np.float32)
    path=tmp_path/'source.wav';sf.write(path,samples,rate,subtype='FLOAT')
    return load_audio(path)


@pytest.mark.parametrize('start,end',[(.75,.25),(.75,0),(.5,.5),(1,0),(0,0),(0,None)])
def test_wrapped_trim_matches_exact_source_order(clip,start,end):
    settings=Settings(start=start,end=end)
    result,rate,_=render(clip,settings)
    a=round(start*rate);b=len(clip.samples) if end is None else round(end*rate)
    expected=clip.samples[a:b] if b>a else np.r_[clip.samples[a:],clip.samples[:b]]
    if not len(expected):expected=clip.samples
    assert np.array_equal(result,expected)
    assert len(result)==round(trim_duration(settings,clip.duration)*rate)
    assert file_hash(clip.path)==clip.sha256


def test_volume_envelope_has_exact_silence_and_no_neutral_processing(clip):
    assert volume_envelope(clip.samples,Settings().volume_curve) is clip.samples
    points=((0,0),(.25,1),(.75,.5),(1,0))
    output=volume_envelope(np.ones((1001,2),np.float32),points)
    assert np.all(output[[0,-1]]==0)
    assert np.all(output[250]==1) and np.all(output[750]==.5)
    assert np.max(np.abs(np.diff(output[:,0])))<.007
    assert np.array_equal(output[:,0],output[:,1])
    cached=render(clip,replace(Settings(),volume_curve=points),cache=RenderCache())
    fresh=render(clip,replace(Settings(),volume_curve=points))
    assert np.array_equal(cached[0],fresh[0])
    for curve in (((0,1),(0,0),(1,1)),((.1,1),(1,1)),((0,-1),(1,1))):
        with pytest.raises(ValueError):render(clip,replace(Settings(),volume_curve=curve))


def test_pitch_envelope_changes_frequency_preserves_duration_and_stereo():
    rate=24000;t=np.arange(3*rate)/rate
    mono=.1*np.sin(2*np.pi*440*t)
    samples=np.stack([mono,mono*.5],axis=1).astype(np.float32)
    curve=((0,0),(.3,0),(.7,12),(1,12))
    output=pitch_envelope(samples,rate,curve)
    assert output.shape==samples.shape and np.isfinite(output).all()
    assert np.corrcoef(output.T)[0,1]>.999
    assert abs(np.linalg.norm(output[:,1])/np.linalg.norm(output[:,0])-.5)<.003
    def frequency(start):
        block=output[round(start*rate):round((start+.2)*rate),0]
        return np.argmax(abs(np.fft.rfft(block*np.hanning(len(block)))))*5
    assert abs(frequency(.3)-440)<10
    assert 570<frequency(1.4)<680
    assert abs(frequency(2.6)-880)<10
    assert pitch_envelope(samples,rate,Settings().pitch_curve) is samples
    cancel=threading.Event();cancel.set()
    with pytest.raises(Cancelled):pitch_envelope(samples,rate,curve,cancel=cancel)


@pytest.mark.parametrize('rate,frames,pitch',[(8000,1,-24),(48000,48,24),(96000,960,-12)])
def test_pitch_envelope_flushes_short_clips(rate,frames,pitch):
    samples=np.ones((frames,1),np.float32)*.1
    output=pitch_envelope(samples,rate,((0,pitch),(1,pitch)))
    assert output.shape==samples.shape and np.isfinite(output).all()
    assert np.max(np.abs(output))>1e-7


def test_grains_are_seeded_stereo_linked_and_do_not_modify_source(clip):
    s=replace(Settings(),granular=True,grain_ms=60,grain_length=1.5,grain_scatter=.6)
    before=clip.samples.copy()
    first=granular_synthesis(clip.samples,clip.rate,s)
    second=granular_synthesis(clip.samples,clip.rate,s)
    different=granular_synthesis(clip.samples,clip.rate,replace(s,grain_seed=2))
    assert first.shape==(round(len(clip.samples)*1.5),2)
    assert np.array_equal(first,second) and not np.array_equal(first,different)
    assert np.array_equal(before,clip.samples) and np.isfinite(first).all()
    paired=np.stack([before[:,0],before[:,0]*.5],axis=1)
    linked=granular_synthesis(paired,clip.rate,s)
    assert np.array_equal(linked[:,1],linked[:,0]*.5)
    freeze=granular_synthesis(paired,clip.rate,replace(s,grain_freeze=True,grain_reverse=1,grain_pitch=4,grain_width=.8))
    assert np.isfinite(freeze).all() and not np.array_equal(freeze,linked)
    for length in (1,24):
        silent=granular_synthesis(np.zeros((length,1),np.float32),clip.rate,s)
        assert not np.any(silent) and len(silent)==round(length*1.5)
    cancel=threading.Event();cancel.set()
    with pytest.raises(Cancelled):granular_synthesis(before,clip.rate,s,cancel)


def test_grain_resampling_suppresses_upward_pitch_aliases():
    rate=48000;t=np.arange(rate)/rate
    high=np.sin(2*np.pi*18000*t).astype(np.float32)[:,None]
    low=np.sin(2*np.pi*2000*t).astype(np.float32)[:,None]
    positions=np.arange(4096)*2.+4000.3
    alias=_sinc_read(high,positions,2)
    passed=_sinc_read(low,positions,2)
    assert np.sqrt(np.mean(alias**2))<np.sqrt(np.mean(passed**2))*.02


def test_stitch_crossfade_laws_duration_resampling_and_boundaries(clip):
    a=np.ones((2400,1),np.float32)*.2
    b=np.ones((1200,2),np.float32)*.2
    clips=[(a,24000,clip),(b,12000,clip)]
    equal,rate,markers=stitch_clips(clips,[(25,'Equal gain')])
    assert equal.shape==(4200,2) and rate==24000
    assert np.allclose(equal[2000:2400],.2,atol=1e-6)
    power,_,_=stitch_clips(clips,[(25,'Equal power')])
    assert abs(float(np.max(power))-.2*np.sqrt(2))<1e-5
    assert markers[1]['start']==.075 and markers[1]['overlap']==.025
    hard,_,_=stitch_clips(clips,[(0,'Equal gain')]);assert len(hard)==4800
    short=np.ones((10,1),np.float32)
    result,_,_=stitch_clips([(short,rate,clip)]*3,[(10000,'Equal gain')]*2)
    assert len(result)==20 and np.all(result==1)


def test_stitched_export_checks_every_source_and_records_provenance(clip,tmp_path):
    path=tmp_path/'other.wav';sf.write(path,clip.samples*.5,clip.rate,subtype='FLOAT');other=load_audio(path)
    samples,rate,markers=stitch_clips([(clip.samples,clip.rate,clip),(other.samples,other.rate,other)],[(30,'Equal gain')])
    sequence=Audio(clip.path,samples,rate,'FLOAT',clip.sha256,((str(clip.path),clip.sha256),(str(other.path),other.sha256)),
                   {'clips':[{'path':str(clip.path)},{'path':str(other.path)}],'markers':markers})
    result=render(sequence,Settings());output=save_render(sequence,Settings(),result,tmp_path,'sequence')
    recipe=json.loads(output.with_suffix('.recipe.json').read_text(encoding='utf-8'))
    assert len(recipe['sources'])==2 and len(recipe['assembly']['clips'])==2
    sf.write(path,other.samples*.5,clip.rate,subtype='FLOAT')
    with pytest.raises(ValueError,match='changed'):save_render(sequence,Settings(),result,tmp_path,'stale')


def test_rename_preserves_audio_recipe_and_refuses_collisions(clip,tmp_path):
    mixed=save_render(clip,Settings(),render(clip,Settings()),tmp_path,'mix')
    digest=file_hash(mixed);new=rename_wav(mixed,'renamed mix')
    assert file_hash(new)==digest and not mixed.exists()
    recipe=json.loads(new.with_suffix('.recipe.json').read_text(encoding='utf-8'))
    assert recipe['output']==new.name and recipe['source']==str(clip.path)
    renamed_source=rename_wav(clip.path,'renamed source')
    assert file_hash(renamed_source)==clip.sha256
    with pytest.raises(ValueError):rename_wav(renamed_source,new.stem)
    with pytest.raises(ValueError):rename_wav(renamed_source,'../escape')
    assert renamed_source.exists()


def test_variants_are_reproducible_distinct_and_bounded():
    base=Settings(pitch=12,gain_db=18,granular=True)
    variants=variant_settings(base,8,.5,83)
    assert variants==variant_settings(base,8,.5,83)
    assert len({s.grain_seed for s in variants})==8
    assert all(-12<=s.pitch<=12 and -24<=s.gain_db<=18 for s in variants)
    assert base==Settings(pitch=12,gain_db=18,granular=True)


@pytest.fixture
def studio(clip,tmp_path):
    from PySide6.QtWidgets import QApplication
    from app import Studio,STYLE
    app=QApplication.instance() or QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
    target=tmp_path/'output';target.mkdir()
    w=Studio(tmp_path/'state',tmp_path,target);w.show();errors=[];w.show_error=errors.append
    def settle():
        deadline=time.monotonic()+60
        while w.busy or w.live_worker or w.live_timer.isActive():
            app.processEvents();time.sleep(.002)
            assert time.monotonic()<deadline
        app.processEvents();assert not errors,errors
    w.load(clip.path);settle()
    try:yield w,settle
    finally:
        w.close()
        deadline=time.monotonic()+15
        while (w.busy or w.live_worker) and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        app.processEvents()


def test_ui_envelopes_wrap_reset_and_live_playback(studio,clip):
    from PySide6.QtCore import Qt,QPoint
    from PySide6.QtTest import QTest
    w,settle=studio;c=w.creative
    assert w.wave.view_mode=='eq'
    w.eq_spins[2].setValue(-4);settle()
    c.view_buttons['volume'].click()
    rect,_,_=w.wave.geometry_parts()
    point=QPoint(round(rect.center().x()),round(rect.bottom()-rect.height()*.2))
    QTest.mouseClick(w.wave,Qt.MouseButton.LeftButton,pos=point);settle()
    assert len(w.current_settings().volume_curve)==5
    assert .35<w.current_settings().volume_curve[2][1]<.45
    assert len(c.envelope_knobs)==5 and c.envelope_knobs[2][2].value() in range(35,46)
    c.view_buttons['pitch'].click()
    assert w.current_settings().volume_curve[2][1]<.5
    c.envelope_knobs[2][2].setValue(120)
    assert w.current_settings().pitch_curve[2][1]==12
    c.envelope_knobs[1][0].setValue(35)
    assert w.current_settings().pitch_curve[1][0]==.35
    QTest.mouseDClick(c.envelope_knobs[2][2],Qt.MouseButton.LeftButton)
    assert w.current_settings().pitch_curve[2][1]==0
    c.reset_view();settle();assert w.current_settings().eq[2]==-4
    c.view_buttons['volume'].click();c.reset_view();settle()
    assert w.current_settings().volume_curve==Settings().volume_curve
    w.wave_trim(.8,.2);settle()
    assert w.current_settings().start==.8 and w.current_settings().end==.2
    assert len(w.result[0])==round(.4*w.result[1])
    w.player.volume=0;w.preview();QTest.qWait(100);stream=w.player.stream
    c.envelope_changed('volume_curve',((0,1),(.5,.25),(1,1)));settle();QTest.qWait(120)
    assert w.player.stream is stream and not w.player.paused
    assert w.player.samples is w.result[0]
    w.load(clip.path);settle()
    assert w.wave.view_mode=='eq' and w.current_settings().volume_curve==Settings().volume_curve


def test_edit_refresh_retains_all_five_points_and_grain_pattern(studio,clip,tmp_path):
    from PySide6.QtWidgets import QApplication
    from app import Studio
    w,settle=studio;c=w.creative
    c.select_view('volume');c.envelope_knobs[2][2].setValue(60)
    c.select_view('pitch');c.envelope_knobs[2][2].setValue(20)
    c.granular_button.click();c.grains['grain_position'].set_value(34);c.seed=381
    settle();expected=w.current_settings()
    w.refresh_app();settle();session=json.loads(w.restart_session.read_text(encoding='utf-8'))
    restored=Studio(tmp_path/'edit-restored',tmp_path,w.target.folder);restored.show();errors=[];restored.show_error=errors.append
    def wait():
        deadline=time.monotonic()+60
        while restored.busy or restored.live_worker or restored.live_timer.isActive():
            QApplication.instance().processEvents();time.sleep(.002);assert time.monotonic()<deadline
        assert not errors,errors
    try:
        restored.load(clip.path,session);wait()
        assert restored.current_settings()==expected and restored.wave.view_mode=='pitch'
        assert not hasattr(restored.creative,'batch')
        assert len(restored.creative.envelope_knobs)==5 and restored.creative.envelope_knobs[2][2].value()==20
    finally:restored.close();wait()


def test_ui_granular_and_multiple_exports_keep_loaded_source(studio,clip):
    w,settle=studio;c=w.creative
    c.granular_button.click();settle()
    assert c.grain_panel.isVisible() and w.current_settings().granular
    first=w.result[0].copy();c.new_pattern();settle();assert not np.array_equal(first,w.result[0])
    c.granular_button.click();settle();assert np.array_equal(w.result[0],render(clip,w.current_settings())[0])
    w.output_name.setText('take')
    loaded=w.audio;settings=w.current_settings();w.generate();settle()
    outputs=sorted(w.target.folder.glob('*.wav'));assert len(outputs)==1
    assert w.audio is loaded and w.current_settings()==settings
    w.controls['gain_db'].set_value(-3);settle();w.generate();settle()
    outputs=sorted(w.target.folder.glob('*.wav'));assert len(outputs)==2
    assert file_hash(outputs[0])!=file_hash(outputs[1])
    assert file_hash(clip.path)==clip.sha256
    w.generate();settle()
    assert len(list(w.target.folder.glob('*.wav')))==3 and w.audio is loaded


def test_ui_stitch_retains_edit_updates_crossfade_and_refreshes(studio,clip,tmp_path):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app import Studio
    w,settle=studio;c=w.creative
    w.controls['gain_db'].set_value(-2);w.wave_trim(.1,.9);settle()
    original=w.current_settings();c.crossfade_button.click();settle()
    c.add_edit();settle();c.append(clip,Settings());settle()
    assert len(c.items)==2 and w.audio.assembly
    assert abs(w.audio.duration-1.72)<1/clip.rate
    w.player.volume=0;w.preview();QTest.qWait(100);stream=w.player.stream
    c.sequence.setCurrentRow(1);c.crossfade.setValue(150);settle();QTest.qWait(120)
    assert w.player.stream is stream and w.play_mode=='processed' and not w.player.paused
    assert abs(w.audio.duration-1.65)<1/clip.rate
    w.output_name.setText('joined');w.generate();settle()
    recipe=json.loads((w.target.folder/'joined.recipe.json').read_text(encoding='utf-8'))
    assert len(recipe['assembly']['clips'])==2
    w.wave_trim(1.2,.3);settle()
    expected=w.current_settings();w.refresh_app();settle()
    session=json.loads(w.restart_session.read_text(encoding='utf-8'))
    restored=Studio(tmp_path/'restored',tmp_path,w.target.folder);restored.show();errors=[];restored.show_error=errors.append
    def wait():
        deadline=time.monotonic()+60
        while restored.busy or restored.live_worker or restored.live_timer.isActive():
            QApplication.instance().processEvents();time.sleep(.002);assert time.monotonic()<deadline
        assert not errors,errors
    try:
        restored.creative.restore_workspace(session);wait()
        assert restored.creative.mode=='stitch' and len(restored.creative.items)==2
        assert restored.current_settings()==expected
        restored.creative.crossfade_button.click();wait()
        assert restored.audio.path==clip.path and restored.current_settings()==original
    finally:restored.close();wait()


def test_ui_rename_does_not_reset_loaded_edit(studio,clip):
    w,settle=studio;w.controls['gain_db'].set_value(-4);settle();settings=w.current_settings()
    for i in range(w.source.list.count()):
        if w.source.list.item(i).data(256)==str(clip.path):
            w.source.list.blockSignals(True);w.source.list.setCurrentRow(i);w.source.list.blockSignals(False)
    w.creative.rename_selected(w.source,'new source')
    assert w.current_settings()==settings and w.audio.path.name=='new source.wav'
    assert file_hash(w.audio.path)==clip.sha256
    w.generate();settle();assert len(list(w.target.folder.glob('*.wav')))==1
