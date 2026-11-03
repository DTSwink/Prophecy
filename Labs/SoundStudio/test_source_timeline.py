"""Source anchored trim display, wrapped selection and live-buffer time mapping."""
from dataclasses import replace
import numpy as np
import pytest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from audio_engine import Settings
from source_timeline import SourceTimeline,mapped_waveform
from visual_audio import analyze
from test_wave_navigation import canvas
from test_creative import clip,studio


@pytest.mark.parametrize('start,end,excluded,positions',[
    (2,8,[(0,2),(8,10)],[(0,2),(3,5),(6,8),(8,8)]),
    (8,2,[(2,8)],[(0,8),(1,9),(2,0),(3,1),(4,2),(6,2)]),
    (8,0,[(0,8)],[(0,8),(1,9),(2,0)]),
    (3,3,[],[(0,3),(6,9),(7,0),(9,2)]),
    (10,0,[],[(0,0),(4,4),(9,9)]),
    (0,10,[],[(0,0),(5,5),(10,10)]),
])
def test_wrap_masks_positions_and_endpoint_tail(start,end,excluded,positions):
    timeline=SourceTimeline(10,Settings(start=start,end=end))
    assert timeline.excluded()==excluded
    for output,source in positions:
        assert timeline.source_position(output)==source
        if output<timeline.length:assert timeline.output_position(source)==pytest.approx(output)


@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('speed',[.5,1,2])
def test_speed_reverse_and_granular_progress_roundtrip(reverse,speed):
    settings=Settings(start=8,end=2,reverse=reverse,speed=speed,granular=True,grain_length=2)
    timeline=SourceTimeline(10,settings,48000)
    for output in np.linspace(.01,timeline.length*timeline.factor-.01,17):
        source=timeline.source_position(output)
        assert timeline.contains(source)
        assert timeline.output_position(source)==pytest.approx(output,abs=1/24000)
    assert timeline.source_position(100)==(8 if reverse else 2)


@pytest.mark.parametrize('start,end,reverse',[(2,8,False),(8,2,False),(8,2,True),(3,3,False),(10,0,False)])
def test_waveform_stays_at_source_coordinates(start,end,reverse):
    rate=1000;source=np.arange(10000,dtype=np.float32)[:,None]/1000000
    settings=Settings(start=start,end=end,reverse=reverse)
    kept=source[int(start*rate):int(end*rate)] if end>start else np.r_[source[int(start*rate):],source[:int(end*rate)]]
    if not len(kept):kept=source.copy()
    if reverse:kept=kept[::-1]
    processed=kept*2
    timeline=SourceTimeline(10,settings,rate)
    peaks,centers=mapped_waveform(source,rate,processed,rate,timeline,0,10,500)
    expected=centers/1000*np.where(timeline.contains(centers),2,1)
    assert np.allclose(peaks.mean(axis=1)[:,0],expected,atol=.000023)


@pytest.mark.parametrize('start,end',[(2,9),(9,2),(5,5),(9,0)])
def test_pixels_show_red_trim_cursor_and_correct_exclusion(canvas,start,end):
    w,data,rate=canvas
    settings=Settings(start=start,end=end)
    kept=data[round(start*rate):round(end*rate)] if end>start else np.r_[data[round(start*rate):],data[:round(end*rate)]]
    w.set_trim(start,end);w.set_result(analyze(kept,rate),settings,kept,rate)
    w.view_seconds=12;w.view_start=0
    w.show_playback(kept,rate,round(.25*rate),'processed',paused=True)
    source_pos=SourceTimeline(12,settings,rate).source_position(.25)
    assert w.source_cursor==pytest.approx(source_pos)
    image=w.grab().toImage();scale=image.devicePixelRatio()
    _,wave,trim=w.geometry_parts()
    color=image.pixelColor(round(w.xpos(source_pos)*scale),round(trim.center().y()*scale))
    assert color.red()>220 and color.green()<100 and color.blue()<120
    # Probe away from waveform centre/handles so only the exclusion overlay
    # affects the known background colour, in both source-time displays.
    selection=SourceTimeline(12,settings,rate)
    for second in (.5,3.5,7.5,10.5):
        x=wave.left()+wave.width()*second/12
        color=image.pixelColor(round(x*scale),round((wave.top()+3)*scale))
        if not selection.contains(second):assert color.blue()<54
        else:assert color.blue()>=54


def test_trim_edit_keeps_paused_source_cursor_and_window_then_live_device(studio):
    w,settle=studio
    w.start_selected(seconds=.55,paused=True)
    w.wave.view_seconds=.3;w.wave.view_start=.4;w.playback_tick()
    before=w.wave.time_window()
    w.wave_trim(.2,.9);settle()
    assert w.player.paused and w.wave.source_cursor==pytest.approx(.55,abs=1/24000)
    assert w.player.position()==pytest.approx(.35,abs=1/24000)
    assert w.wave.time_window()==before
    # Wrapped selection excludes the old cursor: snap playback to a boundary,
    # but do not pan or resize the waveform to follow that trim edit.
    w.wave_trim(.8,.2);settle()
    assert w.wave.time_window()==before
    assert w.wave.source_cursor>=.799 or w.wave.source_cursor<=.201
    w.player.volume=0;w.toggle_play();QTest.qWait(40);stream=w.player.stream
    w.wave_trim(.75,.25);settle();QTest.qWait(50)
    assert w.player.stream is stream and not w.player.paused
    samples,rate,index=w.player.snapshot()
    assert w.wave.timeline(samples).settings.start==.75
    assert w.wave.source_cursor>=.749 or w.wave.source_cursor<=.251
    w.toggle_play()


def test_dragging_trim_does_not_pan_even_during_playback(canvas):
    w,data,rate=canvas;w.show_playback(data,rate,4*rate,'processed')
    before=w.time_window();_,_,trim=w.geometry_parts()
    QTest.mousePress(w,Qt.MouseButton.LeftButton,pos=QPoint(round(w.xpos(0)),round(trim.center().y())))
    QTest.mouseMove(w,QPoint(round(w.xpos(8)),round(trim.center().y())))
    w.show_playback(data,rate,10*rate,'processed')
    assert w.time_window()==before and w.start==pytest.approx(8,abs=.02)
    QTest.mouseRelease(w,Qt.MouseButton.LeftButton,pos=QPoint(round(w.xpos(8)),round(trim.center().y())))
