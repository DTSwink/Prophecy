"""Clean preset integration, caching, cancellation and UI controls."""
from dataclasses import replace
import json
import time
import threading
import numpy as np
import pytest
import soundfile as sf
import audio_engine as engine
from audio_engine import Settings,RenderCache,render,check_cancel,Cancelled,file_hash
from clean_audio import level_match,clean_source
from test_creative import clip,studio


def test_clean_blend_is_exact_and_source_cache_survives_other_edits(clip,monkeypatch):
    calls=[]
    def cleaner(samples,rate,cancel=None):
        calls.append((samples.shape,rate));return samples*.4,['Clear strong test result']
    monkeypatch.setattr(engine,'clean_source',cleaner)
    cache=RenderCache();base=Settings(subtype='FLOAT')
    assert np.array_equal(render(clip,base,cache=cache)[0],clip.samples) and not calls
    assert np.array_equal(render(clip,replace(base,clean=True,clean_amount=0),cache=cache)[0],clip.samples) and not calls
    full=render(clip,replace(base,clean=True),cache=cache)[0]
    half=render(clip,replace(base,clean=True,clean_amount=.5),cache=cache)[0]
    assert np.array_equal(full,clip.samples*.4)
    assert np.allclose(half,clip.samples*.7,atol=1e-8)
    render(clip,replace(base,clean=True,clean_amount=.75,eq=(0,-5,0,0,0)),cache=cache)
    wrapped=render(clip,replace(base,clean=True,start=.8,end=.2),cache=cache)[0]
    assert np.array_equal(wrapped,np.r_[full[round(.8*clip.rate):],full[:round(.2*clip.rate)]])
    assert calls==[(clip.samples.shape,clip.rate)]
    assert file_hash(clip.path)==clip.sha256
    other=replace(clip,samples=clip.samples.copy());render(other,replace(base,clean=True),cache=cache)
    assert len(calls)==2
    for amount in (-.1,1.1,float('nan')):
        with pytest.raises(ValueError):render(clip,replace(base,clean_amount=amount))


def test_clean_level_match_silence_and_cancel():
    t=np.arange(48000)/48000;dry=(.2*np.sin(t*2*np.pi*440))[:,None].astype(np.float32)
    matched,gain=level_match(dry,dry*.5,48000)
    assert gain==pytest.approx(2) and np.array_equal(matched,dry)
    short=np.ones((1,1),np.float32)*.1
    assert np.allclose(level_match(short,short*.5,48000)[0],short)
    silent=np.zeros((48,1),np.float32)
    assert np.array_equal(clean_source(silent,48000)[0],silent)
    cancel=threading.Event();cancel.set()
    with pytest.raises(Cancelled):clean_source(silent,48000,cancel)


def test_clean_ui_default_strength_center_playback_export_and_reset(studio,clip,monkeypatch):
    from PySide6.QtCore import QPoint,Qt
    from PySide6.QtTest import QTest
    w,settle=studio;calls=[]
    monkeypatch.setattr(engine,'clean_source',lambda samples,rate,cancel=None:(calls.append(rate) or samples*.4,['Clear strong']))
    baseline=w.result[0].copy();source_hash=file_hash(clip.path)
    assert not w.clean_button.isChecked() and w.clean_spin.value()==100 and not w.clean_controls.isVisible()
    for width,height in ((1520,970),(1280,800)):
        w.resize(width,height);QTest.qWait(30)
        # Equal-width left/right title columns keep the button at the centre.
        center=w.clean_button.mapTo(w.wave_panel,QPoint(w.clean_button.width()//2,0)).x()
        assert abs(center-w.wave_panel.width()/2)<=2
    w.player.volume=0;w.play_button.click();QTest.qWait(120);stream=w.player.stream
    w.clean_button.click();settle();QTest.qWait(100)
    assert w.current_settings().clean and w.current_settings().clean_amount==1 and w.clean_controls.isVisible()
    assert w.player.stream is stream and not w.player.paused and np.max(abs(w.result[0]))<np.max(abs(baseline))*.5
    w.clean_amount.setValue(50);settle();QTest.qWait(100)
    assert w.current_settings().clean_amount==.5 and len(calls)==1 and w.player.stream is stream
    w.clean_amount.setValue(0);settle();assert np.array_equal(w.result[0],baseline)
    w.clean_reset.click();settle();assert w.clean_spin.value()==100 and len(calls)==1
    w.clean_amount.setFocus();QTest.keyClick(w.clean_amount,Qt.Key.Key_Space)
    assert w.player.paused and w.clean_spin.value()==100
    w.output_name.setText('cleaned');w.generate();settle()
    recipe=json.loads((w.target.folder/'cleaned.recipe.json').read_text(encoding='utf-8'))
    assert recipe['settings']['clean'] and recipe['settings']['clean_amount']==1
    saved,rate=sf.read(w.target.folder/'cleaned.wav',dtype='float32',always_2d=True)
    assert rate==48000 and np.array_equal(saved,w.result[0])
    w.reset_button.click();settle()
    assert not w.clean_button.isChecked() and not w.clean_controls.isVisible() and w.clean_spin.value()==100
    assert np.array_equal(w.result[0],baseline) and file_hash(clip.path)==source_hash


def test_clean_refresh_restores_amount_and_new_sound_clears_it(studio,clip,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QApplication
    from app import Studio
    w,settle=studio
    monkeypatch.setattr(engine,'clean_source',lambda samples,rate,cancel=None:(samples*.4,['Clear strong']))
    w.clean_button.click();w.clean_spin.setValue(37);settle();expected=w.current_settings()
    w.refresh_app();settle();session=json.loads(w.restart_session.read_text(encoding='utf-8'))
    restored=Studio(tmp_path/'clean-restored',tmp_path,w.target.folder);restored.show();errors=[];restored.show_error=errors.append
    def wait():
        deadline=time.monotonic()+30
        while restored.busy or restored.live_worker or restored.live_timer.isActive():
            QApplication.instance().processEvents();time.sleep(.002);assert time.monotonic()<deadline
        assert not errors,errors
    try:
        restored.load(clip.path,session);wait()
        assert restored.current_settings()==expected and restored.clean_controls.isVisible() and restored.clean_spin.value()==37
        restored.load(clip.path);wait()
        assert not restored.clean_button.isChecked() and restored.clean_spin.value()==100
    finally:restored.close();wait()


def test_clean_off_cancels_work_and_missing_plugin_keeps_bypass_usable(studio,monkeypatch):
    from PySide6.QtWidgets import QApplication
    from app import Studio
    w,settle=studio;started=threading.Event();cancelled=threading.Event()
    def waiting(samples,rate,cancel=None):
        started.set()
        try:
            while True:check_cancel(cancel);time.sleep(.01)
        except Cancelled:cancelled.set();raise
    monkeypatch.setattr(engine,'clean_source',waiting)
    w.clean_button.click();deadline=time.monotonic()+5
    while not started.is_set():
        QApplication.instance().processEvents();time.sleep(.005);assert time.monotonic()<deadline
    w.clean_button.click();settle()
    assert cancelled.is_set() and not w.result_settings.clean
    def missing(*args):raise RuntimeError('Clear installation missing')
    monkeypatch.setattr(engine,'clean_source',missing)
    w.clean_button.click();settle();assert 'Clear installation missing' in w.status.text()
    w.clean_button.click();settle();assert w.result is not None and not w.status.problem
