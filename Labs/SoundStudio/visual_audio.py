"""Measured spectrum and waveform views with directly editable parametric EQ."""
from __future__ import annotations
import math
import weakref
from dataclasses import replace
import numpy as np
from scipy.signal import freqz
from scipy.fft import rfft as fast_rfft
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QFont
from PySide6.QtWidgets import QWidget
from audio_engine import Settings, EQ_FREQUENCIES, EQ_CUT, edge_eq_response, peaking_sos
from source_timeline import SourceTimeline,mapped_waveform

COLOR_STOPS = [(20,'#f47783'), (80,'#ffad72'), (250,'#ebd17c'), (1000,'#73e3ba'),
               (4000,'#73c9fa'), (12000,'#b19bfa'), (20000,'#db9ae0')]


def frequency_color(frequency):
    f = max(20,min(20000,float(frequency)))
    for (lo,c1),(hi,c2) in zip(COLOR_STOPS[:-1],COLOR_STOPS[1:]):
        if f <= hi:
            mix = math.log(f/lo)/math.log(hi/lo)
            a,b = QColor(c1),QColor(c2)
            return QColor(round(a.red()*(1-mix)+b.red()*mix),round(a.green()*(1-mix)+b.green()*mix),round(a.blue()*(1-mix)+b.blue()*mix))
    return QColor(COLOR_STOPS[-1][1])


def frequency_label(f):
    return f'{f/1000:.2f}k' if f >= 1000 else f'{f:.0f}'


def analyze(samples, rate):
    """Bounded waveform envelope + stereo-power averaged Hann spectrum."""
    count,channels = samples.shape
    bins = min(1500,count)
    indices = np.linspace(0,count,bins+1,dtype=int)
    peaks = np.stack((np.minimum.reduceat(samples,indices[:-1],axis=0),
                      np.maximum.reduceat(samples,indices[:-1],axis=0)),axis=1)
    nfft = min(8192,2**math.ceil(math.log2(max(64,count))))
    window = np.hanning(nfft)
    # Half-window hop covers the clip without repeatedly analyzing nearly identical windows.
    starts = np.unique(np.linspace(0,max(0,count-nfft),min(160,max(1,math.ceil(count/(nfft//2)))),dtype=int))
    power = np.zeros(nfft//2+1)
    padded = np.pad(samples,((0,max(0,nfft-count)),(0,0)))
    offsets = np.arange(nfft)
    for group in range(0,len(starts),32):
        blocks = padded[starts[group:group+32,None]+offsets[None,:]]
        fft = fast_rfft(blocks*window.astype(np.float32)[None,:,None],axis=1,workers=1)
        power += np.mean(np.abs(fft)**2,axis=2).sum(axis=0)
    magnitude = np.sqrt(power/len(starts))*2/window.sum()
    frequencies = np.fft.rfftfreq(nfft,1/rate)
    grid = np.geomspace(20,min(20000,rate*.49),650)
    spectral = np.interp(grid,frequencies,20*np.log10(np.maximum(magnitude,1e-7)))
    spectral = np.convolve(np.pad(spectral,(2,2),mode='edge'),np.ones(5)/5,mode='valid')
    # Colour the time waveform by the local spectral centroid, never arbitrary stripes.
    color_bins = min(320,count)
    centers = np.linspace(0,count-1,color_bins,dtype=int)
    length = min(1024,count)
    starts = np.clip(centers-512,0,count-length)
    blocks = samples[starts[:,None]+np.arange(length)[None,:]]
    fft = fast_rfft(blocks*np.hanning(length).astype(np.float32)[None,:,None],axis=1,workers=1)
    weights = np.mean(np.abs(fft),axis=2)
    freqs = np.fft.rfftfreq(length,1/rate)
    local_frequency = np.sum(weights*freqs[None,:],axis=1)/np.maximum(1e-15,weights.sum(axis=1))
    return {'peaks':peaks, 'spectrum':spectral, 'frequencies':grid,
            'colors':[frequency_color(f).name() for f in local_frequency],
            'duration':count/rate,'rate':rate,'peak':float(np.max(np.abs(samples),initial=0))}


def eq_response(settings, rate, grid):
    """The actual outer range response and middle RBJ peaking filters."""
    response=edge_eq_response(settings,rate,grid).astype(complex)
    for frequency,gain,q in zip(settings.eq_frequencies[1:4],settings.eq[1:4],settings.eq_q[1:4]):
        if not gain:
            continue
        coefficients=peaking_sos(frequency,gain,q,rate)
        _,h=freqz(coefficients[:3],coefficients[3:],worN=2*np.pi*grid/rate)
        response*=h
    return 20*np.log10(np.maximum(np.abs(response),1e-10))


def playback_analysis(samples, rate, index, view_seconds=2., view_start=None):
    """A measured local FFT and adjustable time window, independent of DSP."""
    count = len(samples)
    nfft = 4096
    start = max(0, min(count-nfft, index-nfft//2))
    block = samples[start:start+nfft]
    block = np.pad(block, ((0,nfft-len(block)),(0,0)))
    window = np.hanning(nfft)
    power = np.mean(np.abs(np.fft.rfft(block*window[:,None],axis=0))**2,axis=1)
    magnitude = np.sqrt(power)*2/window.sum()
    grid = np.geomspace(20,min(20000,rate*.49),650)
    spectrum = np.interp(grid,np.fft.rfftfreq(nfft,1/rate),20*np.log10(np.maximum(magnitude,1e-7)))
    span = max(1,min(count,round(view_seconds*rate)))
    first = max(0,min(count-span,index-round(span*.35) if view_start is None else round(view_start*rate)))
    block = samples[first:first+span]
    bins = min(700,span)
    edges = np.linspace(0,span,bins+1,dtype=int)[:-1]
    peaks = np.stack((np.minimum.reduceat(block,edges,axis=0),np.maximum.reduceat(block,edges,axis=0)),axis=1)
    return {'spectrum':spectrum,'frequencies':grid,'peaks':peaks,'duration':count/rate,
            'view_start':first/rate,'view_duration':span/rate,'peak':float(np.max(np.abs(block))), 'rate':rate}


class AudioDisplay(QWidget):
    trimChanged=Signal(float,float)
    seekRequested=Signal(float)
    bandChanged=Signal(int,float,float,float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(180)
        self.setMouseTracking(True)
        self.source=None
        self.processed=None
        self.duration=0.
        self.start=self.end=0.
        self.cursor=None
        self.cursor_source=False
        self.settings=Settings()
        self.pending=False
        self.drag=None
        self.selected=2
        self.hover=None
        self.zoom=64.
        self.zoom_mode='64×'
        self.playback=None
        self.playback_mode=None
        self.paused=False
        self.original_view=False
        self.source_data=None
        self.processed_data=None
        self.playback_args=None
        self.view_seconds=2.
        self.view_start=None
        self.hold_view=False
        self.render_maps={}
        self.render_settings=Settings()
        self.wave_cache=None
        self.scrub_x=0.
        self.edge_timer=QTimer(self)
        self.edge_timer.setInterval(25)
        self.edge_timer.timeout.connect(self.scroll_scrub)

    def set_audio(self,samples,rate,analysis=None):
        self.reset_navigation()
        self.render_maps.clear()
        self.render_settings=Settings()
        self.wave_cache=None
        self.source_data=(samples,rate)
        self.source_mono_data=(samples.mean(axis=1,keepdims=True),rate) if samples.shape[1]>1 else self.source_data
        self.processed_data=None
        self.source=analysis if analysis is not None else analyze(samples,rate)
        self.duration=self.source['duration']
        self.start,self.end=0,self.duration
        self.processed=None
        self.cursor=None
        self.playback=None
        self.set_zoom(self.zoom_mode)
        self.update()

    def set_result(self,analysis,settings,samples=None,rate=None):
        self.processed=analysis
        if samples is not None:
            self.processed_data=(samples,rate)
            self.remember_render(samples,settings)
        self.render_settings=settings
        self.settings=settings
        self.pending=False
        if self.playback_args and self.paused and self.playback_mode=='processed' and samples is not None:
            seconds=self.timeline(settings=settings).output_position(self.source_cursor)
            index=min(len(samples)-1,round(seconds*rate))
            self.show_playback(samples,rate,index,'processed',paused=True,follow=False)
        self.update()

    def remember_render(self,samples,settings):
        self.render_maps={key:value for key,value in self.render_maps.items() if value[0]() is not None}
        self.render_maps[id(samples)]=(weakref.ref(samples),settings)

    def timeline(self,samples=None,settings=None):
        if settings is None:
            entry=self.render_maps.get(id(samples))
            settings=entry[1] if entry and entry[0]() is samples else self.render_settings
        return SourceTimeline(self.duration,settings,self.source['rate'])

    def set_trim(self,start,end):
        if (start,end)!=(self.start,self.end):self.hold_view=True
        self.start,self.end=start,end
        self.update()

    def waveform_analysis(self):
        start,span,_=self.time_window()
        original=self.playback_mode=='original' if self.playback else self.original_view
        data=(self.playback_args[:2] if self.playback_args else self.processed_data) if not original else None
        samples,rate=data if data else (None,self.source['rate'])
        timeline=self.timeline(samples)
        reference=(self.source if original else self.processed) or self.source
        key=(id(samples),timeline.settings,start,span,id(reference),id(self.source_data[0]))
        if self.wave_cache is None or self.wave_cache[0]!=key:
            source=self.source_mono_data if samples is not None and samples.shape[1]==1 else self.source_data
            peaks,centers=mapped_waveform(*source,samples,rate,timeline,start,span)
            colors=[]
            for position in centers:
                if samples is not None and timeline.contains(position):
                    t=timeline.output_position(position)/reference['duration']
                    palette=reference['colors']
                else:
                    t=position/self.duration;palette=self.source['colors']
                colors.append(palette[min(len(palette)-1,max(0,int(t*len(palette))))])
            self.wave_cache=(key,dict(peaks=peaks,colors=colors,duration=self.duration))
        return self.wave_cache[1]

    def show_playback(self,samples,rate,index,mode,offset=0,paused=False,follow=True):
        self.playback_args=(samples,rate,index,mode,offset,paused)
        span=min(self.duration,self.view_seconds)
        position=index/rate if mode=='original' else self.timeline(samples).source_position(index/rate)
        if self.view_start is None:
            self.view_start=max(0,position-span*.35)
        elif follow and self.drag not in ('scrub','start','end') and not self.hold_view:
            if position<self.view_start:self.view_start=position-span*.1
            elif position>self.view_start+span*.9:self.view_start=position-span*.9
        self.view_start=float(np.clip(self.view_start,0,max(0,self.duration-span)))
        if self.drag not in ('start','end') and self.view_start<=position<=self.view_start+span*.9:
            self.hold_view=False
        frame=playback_analysis(samples,rate,index)
        frame['view_start'],frame['view_duration']=self.view_start,span
        self.playback=frame
        self.playback_mode=mode
        self.paused=paused
        self.cursor=index/rate
        self.source_cursor=position
        self.cursor_source=True
        self.update()

    def clear_playback(self):
        self.edge_timer.stop()
        self.drag=None
        self.playback_args=None
        self.view_start=None
        self.hold_view=False
        self.playback=None
        self.playback_mode=None
        self.cursor=None
        self.update()

    def reset_navigation(self):
        self.clear_playback()
        self.view_seconds=2.

    def refresh_view(self):
        if self.playback_args:
            self.show_playback(*self.playback_args,follow=False)
        else:
            data=self.source_data if self.original_view else (self.processed_data or self.source_data)
            if data:
                self.show_playback(*data,0,'original' if self.original_view else 'processed',paused=True,follow=False)

    def time_window(self):
        if self.playback:
            return self.playback['view_start'],self.playback['view_duration'],self.duration
        return 0.,self.duration,self.duration

    def scrub_to(self,x):
        _,wave,_=self.geometry_parts()
        start,span,duration=self.time_window()
        self.scrub_x=x
        position=min(duration,start+float(np.clip((x-wave.left())/wave.width(),0,1))*span)
        original=self.playback_mode=='original' if self.playback else self.original_view
        data=self.playback_args[0] if self.playback_args else (self.processed_data[0] if self.processed_data else None)
        self.hold_view=False
        self.seekRequested.emit(position if original else self.timeline(data).output_position(position))

    def scroll_scrub(self):
        if self.drag!='scrub':
            self.edge_timer.stop()
            return
        _,wave,_=self.geometry_parts()
        margin=min(40,wave.width()*.08)
        direction=(min(1,(self.scrub_x-(wave.right()-margin))/margin) if self.scrub_x>wave.right()-margin
                   else max(-1,(self.scrub_x-(wave.left()+margin))/margin) if self.scrub_x<wave.left()+margin else 0)
        if not direction:return
        start,span,duration=self.time_window()
        shifted=float(np.clip(start+direction*span*.75*self.edge_timer.interval()/1000,0,max(0,duration-span)))
        if shifted==start:return
        self.view_start=shifted
        self.refresh_view()
        self.scrub_to(self.scrub_x)

    def set_zoom(self,mode):
        self.zoom_mode=mode
        if mode=='Auto':
            self.zoom=min(64,1/max(.015625,(self.source['peak'] if self.source else 1)*1.3))
        else:
            self.zoom=float(mode.replace('×',''))
        self.update()

    def geometry_parts(self):
        left,right=48,self.width()-48
        h=self.height()
        spectrum=QRectF(left,33,right-left,max(30,(h-139)*.58))
        wave=QRectF(left,spectrum.bottom()+43,right-left,max(25,(h-139)*.42))
        trim=QRectF(left,h-41,right-left,24)
        return spectrum,wave,trim

    def max_frequency(self):
        return min(20000,self.source['rate']*.45) if self.source else 20000

    def frequency_x(self,f):
        rect,_,_=self.geometry_parts()
        return rect.left()+math.log(max(20,f)/20)/math.log(self.max_frequency()/20)*rect.width()

    def x_frequency(self,x):
        rect,_,_=self.geometry_parts()
        return 20*(self.max_frequency()/20)**np.clip((x-rect.left())/rect.width(),0,1)

    def gain_y(self,gain):
        rect,_,_=self.geometry_parts()
        gain=max(EQ_CUT,min(15,gain))
        return rect.center().y()-gain/(30 if gain>=0 else -2*EQ_CUT)*rect.height()

    def y_gain(self,y):
        rect,_,_=self.geometry_parts()
        scale=30 if y<=rect.center().y() else -2*EQ_CUT
        gain=float(np.clip((rect.center().y()-y)*scale/rect.height(),EQ_CUT,12))
        if y>=rect.bottom()-5:
            return EQ_CUT
        return 0. if abs(gain)<.6 else gain

    def xpos(self,seconds):
        _,_,rect=self.geometry_parts()
        return rect.left()+seconds/max(self.duration,1e-12)*rect.width()

    def text(self,p,rect,text,color='#bfc5cf',align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter):
        p.setPen(QColor(color));p.drawText(rect,align,text)

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('#3a3d42'))
        spectrum,wave,trim=self.geometry_parts()
        gradient=QLinearGradient(spectrum.left(),0,spectrum.right(),0)
        for f,c in COLOR_STOPS:
            pos=math.log(f/20)/math.log(20000/20)
            gradient.setColorAt(pos,QColor(c))
        p.setFont(QFont('Segoe UI',9))
        self.text(p,QRectF(18,0,self.width()-36,24),'FREQUENCY SPECTRUM'+('  /  PAUSED' if self.paused else '  /  LIVE') if self.playback else 'FREQUENCY SPECTRUM', '#c8cdd5')
        self.text(p,QRectF(18,0,self.width()-36,24),
                  'Updating…' if self.pending else 'Source  ┄    Processed  ━    EQ  ○',
                  '#eacb8b' if self.pending else '#c1c5cc',Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        for f in [20,50,100,250,500,1000,2000,5000,10000,20000]:
            if f>self.max_frequency():continue
            x=self.frequency_x(f)
            p.setPen(QPen(QColor('#555a62'),1))
            p.drawLine(QPointF(x,spectrum.top()),QPointF(x,spectrum.bottom()))
            self.text(p,QRectF(x-25,spectrum.bottom()+3,50,18),frequency_label(f),frequency_color(f).name(),Qt.AlignmentFlag.AlignCenter)
        for level in (-100,-80,-60,-40,-20,0):
            y=spectrum.top()-level/100*spectrum.height()
            p.setPen(QPen(QColor('#494e56'),1))
            p.drawLine(QPointF(spectrum.left(),y),QPointF(spectrum.right(),y))
            self.text(p,QRectF(2,y-10,39,20),str(level),'#b9c0cb',Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        # Correct dBFS orientation: zero at the top, −100 at the bottom.
        if self.source:
            for analysis,original in [(self.source,True),(self.playback or (self.source if self.original_view else self.processed),False)]:
                if analysis is None:continue
                path=QPainterPath()
                valid=analysis['frequencies']<=self.max_frequency()
                xs=spectrum.left()+np.log(analysis['frequencies'][valid]/20)/math.log(self.max_frequency()/20)*spectrum.width()
                ys=spectrum.top()+np.clip(-analysis['spectrum'][valid]/100,0,1)*spectrum.height()
                coords=list(zip(xs,ys))
                if not coords:continue
                path.moveTo(*coords[0])
                for xy in coords[1:]:path.lineTo(*xy)
                if not original:
                    fill=QPainterPath(path)
                    fill.lineTo(coords[-1][0],spectrum.bottom());fill.lineTo(coords[0][0],spectrum.bottom());fill.closeSubpath()
                    p.setOpacity(.13);p.fillPath(fill,gradient);p.setOpacity(1)
                    p.setPen(QPen(gradient,2));p.drawPath(path)
                else:
                    p.setPen(QPen(QColor('#a3abb7'),1,Qt.PenStyle.DashLine));p.drawPath(path)
        # Include the precise band centres so narrow/deep cuts reach their
        # actual minimum instead of disappearing between display samples.
        grid=np.unique(np.r_[np.geomspace(20,self.max_frequency(),500),
                             np.minimum(self.settings.eq_frequencies,self.max_frequency())])
        key=(self.settings.eq,self.settings.eq_frequencies,self.settings.eq_q,self.source['rate'] if self.source else 48000)
        if getattr(self,'response_key',None)!=key:
            self.response_key=key
            self.response_cache=eq_response(self.settings,key[-1],grid)
        response=self.response_cache
        path=QPainterPath()
        for i,(f,gain) in enumerate(zip(grid,response)):
            point=QPointF(self.frequency_x(f),self.gain_y(float(gain)))
            path.moveTo(point) if i==0 else path.lineTo(point)
        p.setPen(QPen(QColor('#e3e7ed'),1.5));p.drawPath(path)
        for gain in (EQ_CUT,-36,-12,0,12):
            self.text(p,QRectF(spectrum.right()+5,self.gain_y(gain)-10,40,20),'CUT' if gain==EQ_CUT else f'{gain:+.0f}','#c1c5cc')
        for i,(freq,gain) in enumerate(zip(self.settings.eq_frequencies,self.settings.eq)):
            x,y=self.frequency_x(min(freq,self.max_frequency())),self.gain_y(gain)
            color=frequency_color(freq)
            if i==self.selected:
                halo=QColor(color);halo.setAlpha(35)
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(halo);p.drawEllipse(QPointF(x,y),17,17)
            p.setPen(QPen(QColor('#3a3d42'),2));p.setBrush(color);p.drawEllipse(QPointF(x,y),7,7)
            self.text(p,QRectF(x-12,y-9,24,18),'L' if i==0 else ('H' if i==4 else str(i+1)),'#252a31',Qt.AlignmentFlag.AlignCenter)
        analysis=self.waveform_analysis() if self.source else None
        duration=analysis['duration'] if analysis else 0
        view_start=self.playback['view_start'] if self.playback else 0
        view_duration=self.playback['view_duration'] if self.playback else duration
        original = self.playback_mode=='original' if self.playback else self.original_view
        title='ORIGINAL WAVEFORM · EFFECTS BYPASSED' if original else 'PROCESSED WAVEFORM · SOURCE TIME'
        if not original and self.settings.granular:title='GRANULAR WAVEFORM · SELECTION PROGRESS'
        self.text(p,QRectF(18,wave.top()-25,self.width()-36,22),title, '#c8cdd5')
        time_text=f'{self.source_cursor:.3f} / ' if self.cursor is not None else ''
        self.text(p,QRectF(18,wave.top()-25,self.width()-36,22),f'{time_text}{duration:.3f} s  ·  View {view_duration:.2f}s  ·  64×',
                  '#c1c5cc',Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        p.fillRect(wave,QColor('#303338'))
        if self.source:
            # Fixed amplitude scale keeps gain changes visible.
            channels=analysis['peaks'].shape[2]
            height=wave.height()/channels
            p.save();p.setClipRect(wave)
            for ch in range(channels):
                middle=wave.top()+(ch+.5)*height
                p.setPen(QPen(QColor('#4b515a'),1));p.drawLine(QPointF(wave.left(),middle),QPointF(wave.right(),middle))
                peaks=analysis['peaks'][:,:,ch]
                for i,(lo,hi) in enumerate(peaks):
                    x=wave.left()+i*wave.width()/max(1,len(peaks)-1)
                    color=analysis['colors'][min(len(analysis['colors'])-1,int(i*len(analysis['colors'])/len(peaks)))]
                    p.setPen(QPen(QColor(color),max(1,wave.width()/len(peaks))))
                    p.drawLine(QPointF(x,middle-float(hi)*self.zoom*height*.43),QPointF(x,middle-float(lo)*self.zoom*height*.43))
            p.restore()
            self.paint_excluded(p,wave,view_start,view_duration)
            if self.cursor is not None and view_duration:
                x=wave.left()+(self.source_cursor-view_start)/view_duration*wave.width()
                if wave.left()<=x<=wave.right():
                    p.fillRect(QRectF(x-16,wave.top(),16,wave.height()),QColor(223,229,240,22))
                    p.setPen(QPen(QColor('#ffffff'),2));p.drawLine(QPointF(x,wave.top()),QPointF(x,wave.bottom()))
        else:
            self.text(p,wave,'Choose a WAV to see its sound','#c1c5cc',Qt.AlignmentFlag.AlignCenter)
        for t in range(5):
            x=wave.left()+wave.width()*t/4
            self.text(p,QRectF(x-30,wave.bottom()+1,60,17),f'{view_start+view_duration*t/4:.2f}s','#b9c0cb',Qt.AlignmentFlag.AlignCenter)
        p.fillRect(trim,QColor('#484e57'))
        if self.source:
            peak=self.source['peaks']
            p.save();p.setClipRect(trim)
            p.setPen(QPen(QColor('#a3abb7'),1))
            for i in range(0,len(peak),2):
                x=trim.left()+i*trim.width()/max(1,len(peak)-1)
                amp=float(np.max(np.abs(peak[i])))*self.zoom
                p.drawLine(QPointF(x,trim.center().y()-amp*10),QPointF(x,trim.center().y()+amp*10))
            p.restore()
            left,right=self.xpos(self.start),self.xpos(self.end)
            ranges=[(left,right)] if self.end>self.start else [(left,trim.right()),(trim.left(),right)]
            for a,b in ranges:p.fillRect(QRectF(a,trim.top(),b-a,trim.height()),QColor(209,221,238,28))
            self.paint_excluded(p,trim,0,self.duration)
            for x,title in [(left,'IN'),(right,'OUT')]:
                p.setPen(QPen(QColor('#d7dde6'),2));p.drawLine(QPointF(x,trim.top()-3),QPointF(x,trim.bottom()+3))
                p.setBrush(QColor('#d7dde6'));p.drawRoundedRect(QRectF(x-3,trim.top(),6,trim.height()),2,2)
                self.text(p,QRectF(max(0,min(x-22,self.width()-45)),trim.bottom()+1,45,17),title,'#b6beca',Qt.AlignmentFlag.AlignCenter)
            if self.cursor is not None:
                x=self.xpos(self.source_cursor)
                p.setPen(QPen(QColor('#ff454f'),3));p.drawLine(QPointF(x,trim.top()-2),QPointF(x,trim.bottom()+2))
        self.text(p,QRectF(1,trim.top(),44,trim.height()),'TRIM','#b9c0cb',Qt.AlignmentFlag.AlignCenter)

    def paint_excluded(self,p,rect,start,span):
        if span<=0:return
        selection=self.timeline(settings=replace(self.settings,start=self.start,end=self.end))
        p.save();p.setClipRect(rect)
        for left,right in selection.excluded():
            a=rect.left()+(left-start)/span*rect.width()
            b=rect.left()+(right-start)/span*rect.width()
            p.fillRect(QRectF(a,rect.top(),b-a,rect.height()),QColor(48,49,52,205))
        p.restore()

    def change_band(self,position):
        index=self.selected
        f=round(float(self.x_frequency(position.x())))
        gain=round(self.y_gain(position.y()),1)
        self.bandChanged.emit(index,f,gain,self.settings.eq_q[index])

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:
            event.ignore();return
        pos=event.position();spectrum,wave,trim=self.geometry_parts()
        if spectrum.contains(pos):
            distances=[math.hypot(self.frequency_x(min(f,self.max_frequency()))-pos.x(),self.gain_y(g)-pos.y()) for f,g in zip(self.settings.eq_frequencies,self.settings.eq)]
            near=int(np.argmin(distances))
            self.selected=near if distances[near]<25 else int(np.argmin([abs(math.log(self.x_frequency(pos.x())/f)) for f in self.settings.eq_frequencies]))
            self.drag='band';self.change_band(pos)
        elif self.source and trim.adjusted(-10,-8,10,8).contains(pos):
            a,b=abs(pos.x()-self.xpos(self.start)),abs(pos.x()-self.xpos(self.end))
            self.drag=('end' if getattr(self,'last_trim','end')=='start' else 'start') if abs(a-b)<1 else ('start' if a<b else 'end')
            self.last_trim=self.drag
            self.mouseMoveEvent(event)
        elif self.source and wave.contains(pos):
            start,span,_=self.time_window()
            self.drag='scrub'
            # Freeze the mapping before seeking: playback updates must not move
            # the time underneath the held mouse. Only the edge timer pans it.
            self.view_start=start
            self.view_seconds=span
            self.scrub_to(pos.x())
            self.edge_timer.start()
            event.accept()
        self.update()

    def mouseMoveEvent(self,event):
        pos=event.position();self.hover=pos
        if self.drag=='band':self.change_band(pos)
        elif self.drag=='scrub':self.scrub_to(pos.x())
        elif self.drag in ('start','end'):
            _,_,trim=self.geometry_parts()
            seconds=float(np.clip((pos.x()-trim.left())/trim.width(),0,1))*self.duration
            self.set_trim(seconds if self.drag=='start' else self.start,seconds if self.drag=='end' else self.end)
            self.trimChanged.emit(self.start,self.end)
        self.update()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        if self.drag=='scrub':self.scrub_to(event.position().x())
        self.edge_timer.stop()
        self.drag=None

    def leaveEvent(self,event):
        self.hover=None;self.update()

    def hideEvent(self,event):
        self.edge_timer.stop()
        self.drag=None
        super().hideEvent(event)

    def wheelEvent(self,event):
        spectrum,wave,_=self.geometry_parts()
        if self.source and wave.contains(event.position()):
            delta=event.angleDelta().y()/120 if event.angleDelta().y() else event.pixelDelta().y()/60
            if not delta:event.accept();return
            start,span,duration=self.time_window()
            anchor=float(np.clip((event.position().x()-wave.left())/wave.width(),0,1))
            self.view_seconds=float(np.clip(span*2**(-delta/3),min(.02,duration),duration))
            self.view_start=float(np.clip(start+anchor*(span-self.view_seconds),0,max(0,duration-self.view_seconds)))
            self.refresh_view()
            event.accept()
        elif spectrum.contains(event.position()):
            i=self.selected
            q=round(float(np.clip(self.settings.eq_q[i]+(.1 if event.angleDelta().y()>0 else -.1),.2,8)),2)
            self.bandChanged.emit(i,self.settings.eq_frequencies[i],self.settings.eq[i],q)
            event.accept()
        else:event.ignore()

    def mouseDoubleClickEvent(self,event):
        spectrum,_,_=self.geometry_parts()
        if spectrum.contains(event.position()):
            i=self.selected
            self.bandChanged.emit(i,min(EQ_FREQUENCIES[i],self.max_frequency()),0,.85)
