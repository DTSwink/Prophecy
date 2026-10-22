"""Measured spectrum and waveform views with directly editable parametric EQ."""
from __future__ import annotations
import math
import numpy as np
from scipy.signal import freqz
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QFont
from PySide6.QtWidgets import QWidget
from audio_engine import Settings, EQ_FREQUENCIES

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
    peaks = np.stack([(samples[a:b].min(axis=0),samples[a:b].max(axis=0)) for a,b in zip(indices[:-1],indices[1:])])
    nfft = 8192
    window = np.hanning(nfft)
    starts = np.unique(np.linspace(0,max(0,count-nfft),min(160,max(1,count//1024)),dtype=int))
    power = np.zeros(nfft//2+1)
    for start in starts:
        block = samples[start:start+nfft]
        if len(block) < nfft:
            block = np.pad(block,((0,nfft-len(block)),(0,0)))
        fft = np.fft.rfft(block*window[:,None],axis=0)
        power += np.mean(np.abs(fft)**2,axis=1)
    magnitude = np.sqrt(power/len(starts))*2/window.sum()
    frequencies = np.fft.rfftfreq(nfft,1/rate)
    grid = np.geomspace(20,min(20000,rate*.49),650)
    spectral = np.interp(grid,frequencies,20*np.log10(np.maximum(magnitude,1e-7)))
    spectral = np.convolve(np.pad(spectral,(2,2),mode='edge'),np.ones(5)/5,mode='valid')
    # Colour the time waveform by the local spectral centroid, never arbitrary stripes.
    color_bins = min(320,count)
    centers = np.linspace(0,count-1,color_bins,dtype=int)
    local_frequency = []
    for center in centers:
        a=max(0,center-512); block=samples[a:min(count,a+1024)]
        if len(block)<8:
            local_frequency.append(1000); continue
        weights=np.mean(np.abs(np.fft.rfft(block*np.hanning(len(block))[:,None],axis=0)),axis=1)
        freqs=np.fft.rfftfreq(len(block),1/rate)
        local_frequency.append(float(np.sum(freqs*weights)/max(1e-15,weights.sum())))
    return {'peaks':peaks, 'spectrum':spectral, 'frequencies':grid,
            'colors':[frequency_color(f).name() for f in local_frequency],
            'duration':count/rate,'rate':rate,'peak':float(np.max(np.abs(samples),initial=0))}


def eq_response(settings, rate, grid):
    """RBJ peaking filters, matching FFmpeg's Q-width equalizers."""
    response=np.ones(len(grid),dtype=complex)
    for frequency,gain,q in zip(settings.eq_frequencies,settings.eq,settings.eq_q):
        if not gain:
            continue
        frequency=min(frequency,rate*.45)
        a=10**(gain/40)
        w=2*np.pi*frequency/rate
        alpha=np.sin(w)/(2*q)
        numerator=[1+alpha*a,-2*np.cos(w),1-alpha*a]
        denominator=[1+alpha/a,-2*np.cos(w),1-alpha/a]
        _,h=freqz(numerator,denominator,worN=2*np.pi*grid/rate)
        response*=h
    return 20*np.log10(np.maximum(np.abs(response),1e-10))


class AudioDisplay(QWidget):
    trimChanged=Signal(float,float)
    seekRequested=Signal(float)
    bandChanged=Signal(int,float,float,float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(280)
        self.setMouseTracking(True)
        self.source=None
        self.processed=None
        self.duration=0.
        self.start=self.end=0.
        self.cursor=None
        self.settings=Settings()
        self.pending=False
        self.drag=None
        self.selected=2
        self.hover=None
        self.zoom=1.
        self.zoom_mode='Auto'
        self.setToolTip('Spectrum: click to place the nearest EQ band; drag to change frequency and gain. Wheel over a band changes its width Q. Double-click resets that band. Bottom source strip: drag IN / OUT to trim.')

    def set_audio(self,samples,rate,analysis=None):
        self.source=analysis if analysis is not None else analyze(samples,rate)
        self.duration=self.source['duration']
        self.start,self.end=0,self.duration
        self.processed=None
        self.cursor=None
        self.set_zoom(self.zoom_mode)
        self.update()

    def set_result(self,analysis,settings):
        self.processed=analysis
        self.settings=settings
        self.pending=False
        self.update()

    def set_zoom(self,mode):
        self.zoom_mode=mode
        if mode=='Auto':
            self.zoom=min(16,1/max(.0625,(self.source['peak'] if self.source else 1)*1.3))
        else:
            self.zoom=float(mode.replace('×',''))
        self.update()

    def geometry_parts(self):
        left,right=48,self.width()-48
        h=self.height()
        spectrum=QRectF(left,33,right-left,max(100,(h-139)*.58))
        wave=QRectF(left,spectrum.bottom()+43,right-left,max(50,(h-139)*.42))
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
        return rect.center().y()-gain/30*rect.height()

    def y_gain(self,y):
        rect,_,_=self.geometry_parts()
        return float(np.clip((rect.center().y()-y)*30/rect.height(),-12,12))

    def xpos(self,seconds):
        _,_,rect=self.geometry_parts()
        return rect.left()+seconds/max(self.duration,1e-12)*rect.width()

    def text(self,p,rect,text,color='#8292ad',align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter):
        p.setPen(QColor(color));p.drawText(rect,align,text)

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('#101621'))
        spectrum,wave,trim=self.geometry_parts()
        gradient=QLinearGradient(spectrum.left(),0,spectrum.right(),0)
        for f,c in COLOR_STOPS:
            pos=math.log(f/20)/math.log(20000/20)
            gradient.setColorAt(pos,QColor(c))
        p.setFont(QFont('Segoe UI',9))
        self.text(p,QRectF(18,0,self.width()-36,24),'FREQUENCY SPECTRUM', '#b2bfd2')
        self.text(p,QRectF(18,0,self.width()-36,24),
                  'Updating…' if self.pending else 'Source  ┄    Processed  ━    EQ  ○',
                  '#eacb8b' if self.pending else '#8b9cb6',Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        for f in [20,50,100,250,500,1000,2000,5000,10000,20000]:
            if f>self.max_frequency():continue
            x=self.frequency_x(f)
            p.setPen(QPen(QColor('#253044'),1))
            p.drawLine(QPointF(x,spectrum.top()),QPointF(x,spectrum.bottom()))
            self.text(p,QRectF(x-25,spectrum.bottom()+3,50,18),frequency_label(f),frequency_color(f).name(),Qt.AlignmentFlag.AlignCenter)
        for level in (-100,-80,-60,-40,-20,0):
            y=spectrum.top()-level/100*spectrum.height()
            p.setPen(QPen(QColor('#1e293b'),1))
            p.drawLine(QPointF(spectrum.left(),y),QPointF(spectrum.right(),y))
            self.text(p,QRectF(2,y-10,39,20),str(level),'#5f708d',Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        # Correct dBFS orientation: zero at the top, −100 at the bottom.
        if self.source:
            for analysis,original in [(self.source,True),(self.processed,False)]:
                if analysis is None:continue
                path=QPainterPath()
                coords=[]
                for f,db in zip(analysis['frequencies'],analysis['spectrum']):
                    if f>self.max_frequency():continue
                    x=self.frequency_x(f)
                    y=spectrum.top()+np.clip(-db/100,0,1)*spectrum.height()
                    coords.append((x,y))
                if not coords:continue
                path.moveTo(*coords[0])
                for xy in coords[1:]:path.lineTo(*xy)
                if not original:
                    fill=QPainterPath(path)
                    fill.lineTo(coords[-1][0],spectrum.bottom());fill.lineTo(coords[0][0],spectrum.bottom());fill.closeSubpath()
                    p.setOpacity(.13);p.fillPath(fill,gradient);p.setOpacity(1)
                    p.setPen(QPen(gradient,2));p.drawPath(path)
                else:
                    p.setPen(QPen(QColor('#56627a'),1,Qt.PenStyle.DashLine));p.drawPath(path)
        grid=np.geomspace(20,self.max_frequency(),500)
        response=eq_response(self.settings,self.source['rate'] if self.source else 48000,grid)
        path=QPainterPath()
        for i,(f,gain) in enumerate(zip(grid,response)):
            point=QPointF(self.frequency_x(f),self.gain_y(float(np.clip(gain,-15,15))))
            path.moveTo(point) if i==0 else path.lineTo(point)
        p.setPen(QPen(QColor('#dce8fb'),1.5));p.drawPath(path)
        for gain in (-12,0,12):
            self.text(p,QRectF(spectrum.right()+5,self.gain_y(gain)-10,40,20),f'{gain:+d}','#8090a9')
        for i,(freq,gain) in enumerate(zip(self.settings.eq_frequencies,self.settings.eq)):
            x,y=self.frequency_x(min(freq,self.max_frequency())),self.gain_y(gain)
            color=frequency_color(freq)
            if i==self.selected:
                halo=QColor(color);halo.setAlpha(35)
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(halo);p.drawEllipse(QPointF(x,y),17,17)
            p.setPen(QPen(QColor('#111722'),2));p.setBrush(color);p.drawEllipse(QPointF(x,y),7,7)
            self.text(p,QRectF(x-12,y-9,24,18),str(i+1),'#15202c',Qt.AlignmentFlag.AlignCenter)
        if self.hover and spectrum.contains(self.hover):
            f=self.x_frequency(self.hover.x())
            p.setPen(QPen(QColor('#677894'),1,Qt.PenStyle.DotLine))
            p.drawLine(QPointF(self.hover.x(),spectrum.top()),QPointF(self.hover.x(),spectrum.bottom()))
            self.text(p,QRectF(max(spectrum.left(),min(self.hover.x()+10,spectrum.right()-175)),spectrum.top()+4,175,22),
                      f'{f:,.0f} Hz  ·  {self.y_gain(self.hover.y()):+.1f} dB',frequency_color(f).name())
        self.text(p,QRectF(18,wave.top()-25,self.width()-36,22),'PROCESSED WAVEFORM', '#b2bfd2')
        duration=self.processed['duration'] if self.processed else self.duration
        self.text(p,QRectF(18,wave.top()-25,self.width()-36,22),f'{duration:.3f} s  ·  Zoom {self.zoom:g}×',
                  '#8496b3',Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        p.fillRect(wave,QColor('#0c121c'))
        if self.source:
            # Same source-derived amplitude scale is held through edits. Peak/normalize changes remain visible.
            analysis=self.processed or self.source
            channels=analysis['peaks'].shape[2]
            height=wave.height()/channels
            p.save();p.setClipRect(wave)
            for ch in range(channels):
                middle=wave.top()+(ch+.5)*height
                p.setPen(QPen(QColor('#263449'),1));p.drawLine(QPointF(wave.left(),middle),QPointF(wave.right(),middle))
                peaks=analysis['peaks'][:,:,ch]
                for i,(lo,hi) in enumerate(peaks):
                    x=wave.left()+i*wave.width()/max(1,len(peaks)-1)
                    color=analysis['colors'][min(len(analysis['colors'])-1,int(i*len(analysis['colors'])/len(peaks)))]
                    p.setPen(QPen(QColor(color),max(1,wave.width()/len(peaks))))
                    p.drawLine(QPointF(x,middle-float(hi)*self.zoom*height*.43),QPointF(x,middle-float(lo)*self.zoom*height*.43))
            p.restore()
            if analysis['peak']*self.zoom>1.16:
                self.text(p,QRectF(wave.left()+6,wave.top()+3,wave.width()-12,20),'View magnified — choose 1× to see full peak height','#e9bf85')
            if self.cursor is not None and duration:
                x=wave.left()+min(1,max(0,self.cursor/duration))*wave.width()
                p.setPen(QPen(QColor('#ffffff'),1));p.drawLine(QPointF(x,wave.top()),QPointF(x,wave.bottom()))
        else:
            self.text(p,wave,'Choose a WAV to see its sound','#7787a0',Qt.AlignmentFlag.AlignCenter)
        for t in range(5):
            x=wave.left()+wave.width()*t/4
            self.text(p,QRectF(x-30,wave.bottom()+1,60,17),f'{duration*t/4:.2f}s','#657894',Qt.AlignmentFlag.AlignCenter)
        p.fillRect(trim,QColor('#151f30'))
        if self.source:
            peak=self.source['peaks']
            p.setPen(QPen(QColor('#5b6982'),1))
            for i in range(0,len(peak),2):
                x=trim.left()+i*trim.width()/max(1,len(peak)-1)
                amp=float(np.max(np.abs(peak[i])))*self.zoom
                p.drawLine(QPointF(x,trim.center().y()-amp*10),QPointF(x,trim.center().y()+amp*10))
            left,right=self.xpos(self.start),self.xpos(self.end)
            p.fillRect(QRectF(left,trim.top(),right-left,trim.height()),QColor(116,200,244,25))
            for x,title in [(left,'IN'),(right,'OUT')]:
                p.setPen(QPen(QColor('#c6d8ef'),2));p.drawLine(QPointF(x,trim.top()-3),QPointF(x,trim.bottom()+3))
                p.setBrush(QColor('#c6d8ef'));p.drawRoundedRect(QRectF(x-3,trim.top(),6,trim.height()),2,2)
                self.text(p,QRectF(max(0,min(x-22,self.width()-45)),trim.bottom()+1,45,17),title,'#95abc7',Qt.AlignmentFlag.AlignCenter)
        self.text(p,QRectF(1,trim.top(),44,trim.height()),'TRIM','#657894',Qt.AlignmentFlag.AlignCenter)

    def change_band(self,position):
        index=self.selected
        f=round(float(self.x_frequency(position.x())))
        gain=round(self.y_gain(position.y()),1)
        self.bandChanged.emit(index,f,gain,self.settings.eq_q[index])

    def mousePressEvent(self,event):
        pos=event.position();spectrum,wave,trim=self.geometry_parts()
        if spectrum.contains(pos):
            distances=[math.hypot(self.frequency_x(min(f,self.max_frequency()))-pos.x(),self.gain_y(g)-pos.y()) for f,g in zip(self.settings.eq_frequencies,self.settings.eq)]
            near=int(np.argmin(distances))
            self.selected=near if distances[near]<25 else int(np.argmin([abs(math.log(self.x_frequency(pos.x())/f)) for f in self.settings.eq_frequencies]))
            self.drag='band';self.change_band(pos)
        elif self.source and trim.adjusted(-10,-8,10,8).contains(pos):
            self.drag='start' if abs(pos.x()-self.xpos(self.start))<abs(pos.x()-self.xpos(self.end)) else 'end'
            self.mouseMoveEvent(event)
        elif self.source and wave.contains(pos):
            duration=self.processed['duration'] if self.processed else self.duration
            self.seekRequested.emit(float(np.clip((pos.x()-wave.left())/wave.width(),0,1))*duration)
        self.update()

    def mouseMoveEvent(self,event):
        pos=event.position();self.hover=pos
        if self.drag=='band':self.change_band(pos)
        elif self.drag in ('start','end'):
            _,_,trim=self.geometry_parts()
            seconds=float(np.clip((pos.x()-trim.left())/trim.width(),0,1))*self.duration
            if self.drag=='start':self.start=min(seconds,max(0,self.end-.001))
            else:self.end=max(seconds,min(self.duration,self.start+.001))
            self.trimChanged.emit(self.start,self.end)
        self.update()

    def mouseReleaseEvent(self,event):
        self.drag=None

    def leaveEvent(self,event):
        self.hover=None;self.update()

    def wheelEvent(self,event):
        spectrum,_,_=self.geometry_parts()
        if spectrum.contains(event.position()):
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
