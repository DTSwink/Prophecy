"""Waveform gestures and callback seeks, without touching the running studio."""
from types import SimpleNamespace
import numpy as np
import pytest
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from audio_engine import Settings
from envelope_display import EnvelopeDisplay
from visual_audio import analyze
from test_creative import clip,studio


@pytest.fixture
def canvas():
    app=QApplication.instance() or QApplication([])
    rate=8000
    t=np.arange(rate*12)/rate
    data=(.005*np.sin(2*np.pi*(100*t+15*t*t)))[:,None].astype(np.float32)
    w=EnvelopeDisplay();w.resize(1100,550)
    analysis=analyze(data,rate)
    w.set_audio(data,rate,analysis);w.set_result(analysis,Settings(),data,rate)
    w.show();app.processEvents()
    yield w,data,rate
    w.close();app.processEvents()


def wheel(w,position,steps):
    event=QWheelEvent(QPointF(position),QPointF(w.mapToGlobal(position)),QPoint(),QPoint(0,steps*120),
                      Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(w,event)
    assert event.isAccepted()


@pytest.mark.parametrize('mode',['eq','volume','pitch'])
@pytest.mark.parametrize('paused',[False,True])
def test_scrubbing_tracks_drag_and_scrolls_at_both_edges(canvas,mode,paused):
    w,data,rate=canvas;w.view_mode=mode
    w.show_playback(data,rate,rate*4,'processed',paused=paused)
    seeks=[]
    def seek(seconds):
        seeks.append(seconds)
        w.show_playback(data,rate,min(len(data)-1,round(seconds*rate)),'processed',paused=paused)
    w.seekRequested.connect(seek)
    _,rect,_=w.geometry_parts();start,span,_=w.time_window()
    a=QPoint(round(rect.left()+rect.width()*.25),round(rect.center().y()))
    b=QPoint(round(rect.left()+rect.width()*.65),a.y())
    QTest.mousePress(w,Qt.MouseButton.LeftButton,pos=a)
    QTest.mouseMove(w,b)
    assert w.drag=='scrub' and w.paused==paused
    assert seeks[-1]==pytest.approx(start+span*.65,abs=.005)
    assert w.time_window()[0]==start
    right=QPoint(round(rect.right()+15),a.y())
    QTest.mouseMove(w,right);before=w.time_window()[0]
    QTest.qWait(140)
    assert w.time_window()[0]>before and seeks[-1]>start+span
    left=QPoint(round(rect.left()-15),a.y())
    QTest.mouseMove(w,left);before=w.time_window()[0]
    QTest.qWait(140)
    assert w.time_window()[0]<before
    QTest.mouseRelease(w,Qt.MouseButton.LeftButton,pos=left)
    assert not w.edge_timer.isActive() and w.drag is None
    count=len(seeks);QTest.qWait(60);assert len(seeks)==count


@pytest.mark.parametrize('mode',['eq','volume','pitch'])
def test_wheel_zoom_anchors_mouse_without_changing_audio_or_seeking(canvas,mode):
    w,data,rate=canvas;w.view_mode=mode
    w.show_playback(data,rate,4*rate,'processed',paused=True)
    seeks=[];w.seekRequested.connect(seeks.append)
    _,rect,_=w.geometry_parts();pos=rect.center().toPoint()
    start,span,_=w.time_window();fraction=(pos.x()-rect.left())/rect.width()
    anchored=start+span*fraction;settings=w.settings
    wheel(w,pos,3)
    new_start,new_span,_=w.time_window()
    assert new_span==pytest.approx(span/2,abs=1/rate)
    assert new_start+new_span*fraction==pytest.approx(anchored,abs=1/rate)
    assert w.settings==settings and w.zoom==64 and not seeks and w.paused
    wheel(w,pos,-60);assert w.time_window()[1]==12 and w.time_window()[0]==0
    wheel(w,pos,90);assert w.time_window()[1]==pytest.approx(.02)
    assert w.source_data[0] is data and w.processed_data[0] is data
    # A shorter processed buffer must not shrink the fixed source timeline.
    w.show_playback(data[:rate//100],rate,0,'processed',paused=True)
    wheel(w,pos,3);assert w.time_window()[1]==pytest.approx(.02)
    w.reset_navigation();assert w.view_seconds==2 and w.playback is None


def test_stopped_zoom_and_playback_follow_at_edge(canvas):
    w,data,rate=canvas;_,rect,_=w.geometry_parts()
    seeks=[];w.seekRequested.connect(seeks.append)
    wheel(w,rect.center().toPoint(),3)
    assert w.time_window()[1]==6 and not seeks
    w.reset_navigation()
    w.show_playback(data,rate,0,'original')
    w.show_playback(data,rate,rate,'original')
    assert w.time_window()[0]==0
    w.show_playback(data,rate,2*rate,'original')
    assert w.time_window()[0]>0
    w.show_playback(data,rate,0,'original')
    assert w.time_window()[0]==0


def test_repeated_seeks_use_existing_stream_and_latest_callback_position(monkeypatch):
    import app as studio
    streams=[]
    class Stream:
        def __init__(self,**kwargs):
            self.callback=kwargs['callback'];self.active=False;self.time=0.;streams.append(self)
        def start(self):self.active=True
        def abort(self):self.active=False
        def close(self):pass
    monkeypatch.setattr(studio.sd,'OutputStream',Stream)
    p=studio.Player();data=np.arange(48000*3,dtype=np.float32)[:,None]/500000
    p.play(data,48000);stream=p.stream
    for position in (1,.5,2,.75):p.seek(position)
    assert p.stream is stream and len(streams)==1 and p.position()==.75
    out=np.empty((256,2),np.float32)
    stream.callback(out,256,SimpleNamespace(outputBufferDacTime=0.),SimpleNamespace(output_underflow=False))
    assert np.array_equal(out[:,0],data[36000:36256,0])
    assert not p.seek_requests and p.position()==.75
    p.pause();p.seek(1.5)
    assert p.paused and p.position()==1.5 and len(streams)==1
    p.stop()


def test_studio_drag_keeps_live_device_and_paused_state(studio):
    w,settle=studio
    w.player.volume=0  # Exercise the real device silently in an isolated studio.
    w.play_button.click();QTest.qWait(80)
    stream=w.player.stream
    w.wave.view_seconds=.2
    w.player.seek(.4);w.playback_tick()
    _,rect,_=w.wave.geometry_parts()
    a=QPoint(round(rect.left()+rect.width()*.3),round(rect.center().y()))
    b=QPoint(round(rect.left()+rect.width()*.7),a.y())
    settings=w.current_settings()
    for original in (False,True):
        w.play_original_check.setChecked(original);QTest.qWait(50)
        QTest.mousePress(w.wave,Qt.MouseButton.LeftButton,pos=a)
        QTest.mouseMove(w.wave,b);QTest.qWait(60)
        QTest.mouseRelease(w.wave,Qt.MouseButton.LeftButton,pos=b)
        assert w.player.stream is stream and not w.player.paused
        assert w.play_mode==('original' if original else 'processed')
    w.toggle_play();assert w.player.paused
    start,span,_=w.wave.time_window()
    QTest.mousePress(w.wave,Qt.MouseButton.LeftButton,pos=a)
    QTest.mouseMove(w.wave,b)
    QTest.mouseRelease(w.wave,Qt.MouseButton.LeftButton,pos=b)
    assert w.player.paused and w.player.stream is None
    assert w.player.position()==pytest.approx(start+span*(b.x()-rect.left())/rect.width(),abs=1/w.player.rate)
    position=w.player.position();wheel(w.wave,b,3)
    assert w.player.position()==position and w.current_settings()==settings
    w.controls['gain_db'].set_value(-3);settle()
    assert w.player.paused and w.player.position()==position
    w.reset_button.click();settle()
    assert w.wave.view_seconds==2 and w.wave.drag is None
