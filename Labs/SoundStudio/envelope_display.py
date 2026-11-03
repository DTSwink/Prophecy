"""Shared audio canvas with EQ, volume and pitch editing views."""
from dataclasses import replace
import numpy as np
from PySide6.QtCore import Qt,QRectF,QPointF,Signal
from PySide6.QtGui import QPainter,QColor,QPen,QPainterPath,QFont
from visual_audio import AudioDisplay
from creative_audio import envelope_values


class EnvelopeDisplay(AudioDisplay):
    envelopeChanged=Signal(str,object)

    def __init__(self):
        super().__init__()
        self.view_mode='eq'
        self.point_selected=0
        self.sequence_markers=[]

    def curve(self):
        return self.settings.volume_curve if self.view_mode=='volume' else self.settings.pitch_curve

    def point_xy(self,point):
        rect,_,_=self.geometry_parts()
        low,high=(0,2) if self.view_mode=='volume' else (-24,24)
        return QPointF(rect.left()+point[0]*rect.width(),rect.bottom()-(point[1]-low)/(high-low)*rect.height())

    def edit_point(self,position):
        points=list(self.curve());i=self.point_selected
        rect,_,_=self.geometry_parts()
        low,high=(0,2) if self.view_mode=='volume' else (-24,24)
        t=float(np.clip((position.x()-rect.left())/rect.width(),0,1))
        if i==0:t=0.
        elif i==len(points)-1:t=1.
        else:t=float(np.clip(t,points[i-1][0]+.001,points[i+1][0]-.001))
        value=round(float(np.clip(low+(rect.bottom()-position.y())/rect.height()*(high-low),low,high)),2)
        neutral=1 if self.view_mode=='volume' else 0
        if abs(value-neutral)<(.035 if neutral else .5):value=float(neutral)
        points[i]=(t,value)
        self.publish(points)

    def publish(self,points):
        key='volume_curve' if self.view_mode=='volume' else 'pitch_curve'
        points=tuple(tuple(p) for p in points)
        self.settings=replace(self.settings,**{key:points})
        self.envelopeChanged.emit(key,points);self.update()

    def paintEvent(self,event):
        super().paintEvent(event)
        rect,wave,_=self.geometry_parts()
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.view_mode!='eq':
            color=QColor('#ffbf7f' if self.view_mode=='volume' else '#bcadff')
            p.fillRect(QRectF(0,0,self.width(),rect.bottom()+22),QColor('#3a3d42'))
            p.setFont(QFont('Segoe UI',9))
            self.text(p,QRectF(18,0,self.width()-36,24),self.view_mode.upper()+' ENVELOPE',color.name())
            self.text(p,QRectF(18,0,self.width()-36,24),'5 points  ·  Drag time / level  ·  Double-click neutral',
                      '#c1c5cc',Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
            levels=((0,1,2) if rect.height()<90 else (0,.5,1,1.5,2)) if self.view_mode=='volume' else ((-24,0,24) if rect.height()<90 else (-24,-12,0,12,24))
            duration=(self.processed or self.source or {}).get('duration',0)
            for level in levels:
                y=self.point_xy((0,level)).y()
                p.setPen(QPen(QColor('#555a62'),1));p.drawLine(QPointF(rect.left(),y),QPointF(rect.right(),y))
                title=f'{level*100:g}%' if self.view_mode=='volume' else f'{level:+g}'
                self.text(p,QRectF(0,y-10,42,20),title,'#c1c5cc',Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
            for i in range(5):
                x=rect.left()+rect.width()*i/4
                p.setPen(QPen(QColor('#494e56'),1));p.drawLine(QPointF(x,rect.top()),QPointF(x,rect.bottom()))
                self.text(p,QRectF(x-30,rect.bottom()+2,60,18),f'{duration*i/4:.2f}s','#c1c5cc',Qt.AlignmentFlag.AlignCenter)
            reference=self.processed or self.source
            if reference:
                p.save();p.setClipRect(rect)
                peaks=reference['peaks'];p.setPen(QPen(QColor('#525963'),1))
                for i in range(0,len(peaks),2):
                    amp=min(1,float(np.max(np.abs(peaks[i])))*self.zoom)
                    x=rect.left()+i/max(1,len(peaks)-1)*rect.width()
                    p.drawLine(QPointF(x,rect.center().y()-amp*rect.height()*.4),QPointF(x,rect.center().y()+amp*rect.height()*.4))
                p.restore()
            positions=np.linspace(0,1,500);values=envelope_values(self.curve(),positions)
            path=QPainterPath()
            for i,point in enumerate(zip(positions,values)):
                xy=self.point_xy(point)
                path.moveTo(xy) if i==0 else path.lineTo(xy)
            p.setPen(QPen(color,2));p.drawPath(path)
            for i,point in enumerate(self.curve()):
                xy=self.point_xy(point);p.setBrush(color);p.setPen(QPen(QColor('#3a3d42'),2));p.drawEllipse(xy,6,6)
                self.text(p,QRectF(xy.x()-12,xy.y()-10,24,20),str(i+1),'#252a31',Qt.AlignmentFlag.AlignCenter)
            if self.cursor is not None and duration:
                x=rect.left()+self.cursor/duration*rect.width()
                p.setPen(QPen(QColor('#edf0f3'),1));p.drawLine(QPointF(x,rect.top()),QPointF(x,rect.bottom()))
        if (self.sequence_markers and not self.playback and not self.settings.granular and not self.settings.reverse
                and self.settings.start==0 and self.settings.end in (None,self.duration)):
            duration=(self.processed or self.source or {}).get('duration',1)
            for marker in self.sequence_markers[1:]:
                x=wave.left()+marker['start']/self.settings.speed/duration*wave.width()
                end=x+marker['overlap']/self.settings.speed/duration*wave.width()
                p.fillRect(QRectF(x,wave.top(),max(2,end-x),wave.height()),QColor(205,216,234,40))
                p.setPen(QPen(QColor('#d2d9e3'),1));p.drawLine(QPointF(x,wave.top()),QPointF(x,wave.bottom()))

    def mousePressEvent(self,event):
        rect,_,_=self.geometry_parts()
        if self.view_mode=='eq' or not rect.adjusted(-8,-8,8,8).contains(event.position()):
            return super().mousePressEvent(event)
        points=list(self.curve())
        distances=[(self.point_xy(point)-event.position()).manhattanLength() for point in points]
        i=int(np.argmin(distances))
        if event.button()==Qt.MouseButton.RightButton:
            return
        if distances[i]>20:i=int(np.argmin([abs(self.point_xy(point).x()-event.position().x()) for point in points]))
        self.point_selected=i;self.drag='envelope';self.edit_point(event.position())

    def mouseMoveEvent(self,event):
        if self.drag=='envelope':self.edit_point(event.position())
        else:super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self,event):
        rect,_,_=self.geometry_parts()
        if self.view_mode!='eq' and rect.adjusted(-8,-8,8,8).contains(event.position()):
            points=list(self.curve());i=int(np.argmin([(self.point_xy(p)-event.position()).manhattanLength() for p in points]))
            points[i]=(points[i][0],1 if self.view_mode=='volume' else 0);self.publish(points)
        else:super().mouseDoubleClickEvent(event)

    def wheelEvent(self,event):
        _,wave,_=self.geometry_parts()
        if self.view_mode=='eq' or wave.contains(event.position()):super().wheelEvent(event)
        else:event.ignore()
