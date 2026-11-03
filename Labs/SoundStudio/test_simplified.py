"""Regression checks for the lean UI, complete resets and playable safe output."""
from dataclasses import replace
import numpy as np
import soundfile as sf
import pytest
from audio_engine import Settings,render,load_audio,save_render,file_hash
from test_creative import clip,studio


def test_automatic_safety_preserves_quiet_audio_and_fixes_overload(clip,tmp_path):
    neutral=Settings(auto_protect=True)
    assert np.array_equal(render(clip,neutral)[0],clip.samples)
    settings=replace(neutral,gain_db=18,volume_curve=((0,2),(1,2)),sample_rate=48000,subtype='PCM_16',channels='Mono')
    result=render(clip,settings)
    assert result[0].shape==(48000,1) and not result[2]['export_blocked']
    assert result[2]['automatic_protection'] and result[2]['protection_gain_db']<0
    assert result[2]['estimated_true_peak_dbtp']<=-1
    saved=save_render(clip,settings,result,tmp_path,'safe')
    samples,rate=sf.read(saved,dtype='float32',always_2d=True)
    assert rate==48000 and sf.info(saved).subtype=='PCM_16' and np.array_equal(samples,result[0])
    assert file_hash(clip.path)==clip.sha256


def test_visible_knob_resets_in_every_view_and_effect(studio):
    w,settle=studio;c=w.creative
    for i in range(5):
        w.eq_spins[i].setValue(-8);w.eq_freqs[i].setValue(300);w.eq_widths[i].setValue(2)
        w.eq_resets[i].click()
        assert w.eq_spins[i].value()==0 and w.eq_widths[i].value()==.85
        assert w.eq_freqs[i].value()==min(Settings().eq_frequencies[i],w.eq_freqs[i].maximum())
    for mode,changed,neutral in [('volume',35,100),('pitch',60,0)]:
        c.select_view(mode)
        for i in range(5):
            c.envelope_knobs[i][2].setValue(changed);c.envelope_resets[i].click()
            assert c.envelope_knobs[i][2].value()==neutral
    w.pitch_spin.setValue(5);w.pitch_reset.click();assert w.pitch_spin.value()==0
    for key,control in w.controls.items():
        control.set_value(control.spin.minimum());control.reset_button.click()
        assert control.value()==control.default
    assert w.controls['end'].value()==w.audio.duration
    c.granular_button.click();settle();assert c.grain_panel.isVisible()
    for control in c.grains.values():
        control.set_value(control.spin.minimum());control.reset_button.click()
        assert control.value()==control.default
    c.granular_button.click();settle();assert not w.current_settings().granular


def test_reset_all_clears_hidden_effects_sequence_and_transport_options(studio,clip):
    w,settle=studio;c=w.creative
    c.crossfade_button.click();settle();c.add_edit();settle();c.append(clip,Settings());settle()
    c.sequence.setCurrentRow(1);c.crossfade.setValue(150);settle();c.curve.setCurrentIndex(1);settle()
    c.join_reset.click();settle();assert c.items[1]['fade']==80 and c.items[1]['curve']=='Equal gain'
    c.granular_button.click();settle();c.grains['grain_ms'].set_value(150);c.new_pattern();c.freeze.setChecked(True)
    c.select_view('volume');c.envelope_knobs[2][2].setValue(45)
    c.select_view('pitch');c.envelope_knobs[2][2].setValue(20)
    w.controls['gain_db'].set_value(6);w.controls['fade_in_ms'].set_value(30);w.controls['denoise'].set_value(2)
    w.controls['compression'].set_value(50);w.eq_spins[2].setValue(-10);w.reverse.setChecked(True)
    w.formants.setChecked(True);w.protect.setChecked(True);w.normalize.setChecked(True);w.normalize_target.setValue(-7)
    w.loop.setChecked(False);w.play_original_check.setChecked(True);w.output_name.setText('changed')
    w.wave_trim(.6,.2);settle();w.reset_button.click();settle()
    expected=Settings(end=clip.duration,sample_rate=48000,subtype='PCM_16',channels='Mono',auto_protect=True,
                      eq_frequencies=(80,250,1000,4000,10800))
    assert w.audio.path==clip.path and w.current_settings()==expected
    assert c.mode=='edit' and not c.items and c.edit_session is None and c.edit_audio is None
    assert c.crossfade.value()==80 and c.curve.currentIndex()==0 and c.seed==1
    assert not c.grain_panel.isVisible() and not c.sequence_panel.isVisible()
    assert not c.crossfade_button.isChecked() and not c.granular_button.isChecked() and w.wave.view_mode=='eq'
    assert w.loop.isChecked() and not w.play_original_check.isChecked()
    assert w.output_name.text()==clip.path.stem+'_mix'


def test_clipped_edit_can_play_save_repeatedly_and_bypass(studio,clip):
    from PySide6.QtTest import QTest
    w,settle=studio;c=w.creative
    w.controls['gain_db'].set_value(18)
    c.envelope_changed('volume_curve',tuple((i/4,2.) for i in range(5)));settle()
    assert w.result[2]['automatic_protection'] and not w.result[2]['export_blocked']
    assert 'prevent clipping' in w.status.text()
    w.player.volume=0;w.play_button.click();QTest.qWait(150);stream=w.player.stream
    assert stream is not None and w.play_mode=='processed' and np.max(np.abs(w.player.samples))<1
    assert 'prevent clipping' in w.status.text()
    w.output_name.setText('repeat');settings=w.current_settings();loaded=w.audio
    w.generate_button.click();settle();QTest.qWait(100)
    assert w.player.stream is stream and w.audio is loaded and w.current_settings()==settings
    w.controls['gain_db'].set_value(0);settle();w.generate_button.click();settle()
    outputs=sorted(w.target.folder.glob('*.wav'))
    assert len(outputs)==2 and file_hash(outputs[0])!=file_hash(outputs[1])
    assert all(sf.info(path).samplerate==48000 and sf.info(path).channels==1 and sf.info(path).subtype=='PCM_16' for path in outputs)
    assert not w.status.problem and w.player.stream is stream
    w.play_original_check.click();QTest.qWait(150)
    assert w.play_mode=='original' and w.player.stream is stream
    w.play_original_check.click();QTest.qWait(150)
    assert w.play_mode=='processed' and w.current_settings().gain_db==0
    assert file_hash(clip.path)==clip.sha256


def test_header_buttons_messages_and_removed_ui(studio,monkeypatch):
    from PySide6.QtWidgets import QPushButton,QCheckBox,QMessageBox
    from PySide6.QtCore import QPoint
    w,settle=studio;c=w.creative
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:pytest.fail('Error must stay in the header'))
    # Use the actual handler; the shared fixture normally collects errors.
    from app import Studio
    Studio.show_error(w,'Example error')
    assert w.status.text()=='Example error' and w.status.mapTo(w,QPoint(0,0)).y()<60
    w.status.setText('Playing');assert w.status.text()=='Example error'
    assert w.play_original_check.objectName()=='original' and isinstance(w.play_original_check,QPushButton)
    assert w.reset_button.objectName()=='resetAll'
    assert w.source.isAncestorOf(w.refresh_app_button)
    forbidden={'Guide','Folders','LIVE PREVIEW','Grain controls','Multiple takes'}
    assert not forbidden.intersection(x.text() for x in w.findChildren(QPushButton)+w.findChildren(QCheckBox))
    assert not hasattr(w,'preview_info') and not hasattr(w,'rate') and not hasattr(w,'channel_mode')
    c.granular_button.click();settle();assert c.grain_panel.isVisible()
    c.crossfade_button.click();settle();assert c.mode=='stitch' and c.sequence_panel.isVisible()
    c.add_edit();settle();c.granular_button.click();settle();assert c.grain_panel.isVisible()
    c.crossfade_button.click();assert c.mode=='stitch' and c.sequence_panel.isVisible()
    c.granular_button.click();assert c.grain_panel.isVisible() and c.granular_button.isChecked()
    c.granular_button.click();settle();assert c.sequence_panel.isVisible() and not c.granular_button.isChecked()
    c.crossfade_button.click();settle();assert c.mode=='edit'


def test_magnified_source_strip_never_paints_over_spectrum(studio):
    from PySide6.QtGui import QImage
    w,settle=studio;settle()
    original=w.wave.source['peaks']
    def pixels():
        image=w.wave.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        return np.frombuffer(image.bits(),np.uint8).reshape(image.height(),image.bytesPerLine()).copy(),image.devicePixelRatio()
    try:
        w.wave.source['peaks']=original*0;before,scale=pixels()
        w.wave.source['peaks']=original*200;after,_=pixels()
        _,_,trim=w.wave.geometry_parts()
        top=int(trim.top()*scale);bottom=int((trim.bottom()+2)*scale)
        assert np.array_equal(before[:top],after[:top])
        assert np.array_equal(before[bottom:],after[bottom:])
        assert not np.array_equal(before,after)
    finally:w.wave.source['peaks']=original
