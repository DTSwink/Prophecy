"""Lean creative panels and sequence workflow for the native studio."""
from dataclasses import asdict,replace
from pathlib import Path
import secrets
import copy
import numpy as np
from PySide6.QtCore import Qt,QSize
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QHBoxLayout,QVBoxLayout,QGridLayout,
                              QCheckBox,QSpinBox,QDoubleSpinBox,QComboBox,QListWidget,QListWidgetItem,QInputDialog,QSlider,QSizePolicy,QFileDialog)
from audio_engine import Settings,Audio,RenderCache,load_audio,render,save_render,output_stem,check_cancel
from creative_audio import stitch_clips,variant_settings,rename_wav,envelope_values
from visual_audio import analyze


class CreativeTools:
    def __init__(self,w,main,header,surface,button,Control):
        self.w=w;self.mode='edit';self.items=[];self.edit_audio=None;self.edit_session=None
        self.main=main;self.grain_sidebar=False;self.sequence_sidebar=False;self.adapting=False
        self.volume_curve=Settings().volume_curve;self.pitch_curve=Settings().pitch_curve
        self.seed=1;self.restoring=False
        self.crossfade_button=button('Crossfade',self.crossfade_clicked);self.crossfade_button.setCheckable(True)
        header.insertWidget(2,self.crossfade_button)
        self.granular_button=button('Granular',lambda:None);self.granular_button.setCheckable(True)
        header.insertWidget(2,self.granular_button)
        self.granular_button.clicked.connect(self.toggle_granular)
        views=QHBoxLayout();views.setSpacing(4);self.view_buttons={}
        for mode,title in [('eq','EQ'),('volume','Volume'),('pitch','Pitch')]:
            b=button(title,lambda checked=False,m=mode:self.select_view(m));b.setCheckable(True)
            b.setMinimumWidth(74);self.view_buttons[mode]=b;views.addWidget(b)
        views.addStretch();views.addWidget(button('Reset view',self.reset_view))
        surface.insertLayout(2,views)
        w.wave.envelopeChanged.connect(self.envelope_changed)
        self.envelope_strip=QFrame();self.envelope_strip.setObjectName('eqStrip')
        env_layout=QHBoxLayout(self.envelope_strip);env_layout.setContentsMargins(4,6,4,7);env_layout.setSpacing(12)
        self.envelope_knobs=[];self.envelope_resets=[]
        for i in range(5):
            column=QVBoxLayout();row=QHBoxLayout();row.setSpacing(4)
            title=QLabel(str(i+1));row.addWidget(title)
            position=QDoubleSpinBox();position.setDecimals(1);position.setRange(0,100);position.setSuffix(' % t')
            position.setFixedWidth(73);position.setKeyboardTracking(False);row.addWidget(position)
            value=QDoubleSpinBox();value.setFixedWidth(65);value.setKeyboardTracking(False);row.addWidget(value)
            reset=button('↺',lambda checked=False,index=i:self.reset_point(index),'knobReset');self.envelope_resets.append(reset)
            slider=QSlider(Qt.Orientation.Horizontal);column.addLayout(row)
            slider_row=QHBoxLayout();slider_row.setSpacing(3);slider_row.addWidget(slider,1);slider_row.addWidget(reset)
            column.addLayout(slider_row);env_layout.addLayout(column,1)
            self.envelope_knobs.append((position,value,slider))
            position.valueChanged.connect(lambda number,index=i:self.knob_changed(index,'time',number))
            value.valueChanged.connect(lambda number,index=i:self.knob_changed(index,'value',number))
            slider.valueChanged.connect(lambda number,index=i:self.knob_changed(index,'slider',number))
            slider.mouseDoubleClickEvent=lambda event,index=i:self.reset_point(index)
        surface.insertWidget(2,self.envelope_strip)
        self.select_view('eq')
        self.grain_panel=QFrame();self.grain_panel.setObjectName('strip')
        layout=QVBoxLayout(self.grain_panel);layout.setContentsMargins(10,7,10,8);layout.setSpacing(7)
        row=QHBoxLayout();self.grain_header=row;row.addWidget(QLabel('GRAIN CLOUD'));row.addStretch()
        self.freeze=QCheckBox('Freeze position');row.addWidget(self.freeze);self.freeze.toggled.connect(w.edited)
        row.addWidget(button('New pattern',self.new_pattern));layout.addLayout(row)
        self.grains={};grid=QGridLayout();self.grain_grid=grid;grid.setHorizontalSpacing(16);grid.setVerticalSpacing(8)
        specs=[('grain_ms','Size',10,250,80,1,' ms'),('grain_density','Density',1,12,4,.5,' ×'),
               ('grain_position','Position',0,100,0,1,' %'),('grain_scatter','Scatter',0,100,25,1,' %'),
               ('grain_pitch','Pitch spread',0,12,0,.1,' st'),
               ('grain_reverse','Reverse chance',0,100,0,1,' %'),('grain_length','Length',25,400,100,1,' %')]
        for i,(key,*args) in enumerate(specs):
            control=Control(*args);control.spin.setFixedWidth(75);control.changed.connect(w.edited)
            control.layout().setSpacing(3);control.slider.setFixedHeight(12)
            control.setStyleSheet('QLabel {font-size:11px;} QDoubleSpinBox {font-size:11px;padding:2px;}')
            self.grains[key]=control;grid.addWidget(control,i//4,i%4)
        layout.addLayout(grid)
        hint=QLabel('Size shapes detail · Density layers grains · Scatter explores the source · Freeze holds Position')
        hint.setWordWrap(True);hint.setObjectName('muted');layout.addWidget(hint);layout.addStretch(1)
        main.insertWidget(0,self.grain_panel);self.grain_panel.hide()
        self.sequence_panel=QFrame();self.sequence_panel.setObjectName('strip')
        layout=QVBoxLayout(self.sequence_panel);layout.setContentsMargins(10,8,10,8);layout.setSpacing(6)
        row=QHBoxLayout();self.sequence_header=row;row.addWidget(QLabel('SEQUENCE'))
        for title,fn in [('Add source',lambda:self.add_selected(w.source)),('Add mix',lambda:self.add_selected(w.target)),
                         ('Add current edit',self.add_edit)]:
            row.addWidget(button(title,fn))
        moves=QWidget();moves_row=QHBoxLayout(moves);moves_row.setContentsMargins(0,0,0,0);moves_row.setSpacing(4)
        for title,fn in [('←',lambda:self.move(-1)),('→',lambda:self.move(1)),('Remove',self.remove)]:moves_row.addWidget(button(title,fn))
        row.addWidget(moves)
        row.addStretch();layout.addLayout(row)
        self.sequence=QListWidget();self.sequence.setFlow(QListWidget.Flow.LeftToRight);self.sequence.setWrapping(False)
        self.sequence.setFixedHeight(72);self.sequence.setSpacing(4);layout.addWidget(self.sequence)
        self.sequence.currentRowChanged.connect(self.select_join)
        row=QHBoxLayout();self.sequence_join=row;row.addWidget(QLabel('Crossfade into selected clip'))
        self.crossfade=QDoubleSpinBox();self.crossfade.setRange(0,10000);self.crossfade.setDecimals(0)
        self.crossfade.setSuffix(' ms');self.crossfade.setValue(80);self.crossfade.setFixedWidth(85)
        self.crossfade.setKeyboardTracking(False);row.addWidget(self.crossfade)
        self.curve=QComboBox();self.curve.addItems(['Equal gain','Equal power']);row.addWidget(self.curve)
        self.join_reset=button('↺',self.reset_join,'knobReset');row.addWidget(self.join_reset)
        self.sequence_info=QLabel('Add clips from either folder, then arrange them.');self.sequence_info.setObjectName('muted')
        self.sequence_info.setWordWrap(True)
        row.addWidget(self.sequence_info,1);layout.addLayout(row)
        self.crossfade.valueChanged.connect(self.join_changed);self.curve.currentIndexChanged.connect(self.join_changed)
        main.insertWidget(0,self.sequence_panel);self.sequence_panel.hide()
        for pane in (w.source,w.target):
            pane.layout().insertWidget(pane.layout().count()-1,button('Rename selected',lambda checked=False,p=pane:self.rename_selected(p)))

    def values(self):
        values={key:control.value() for key,control in self.grains.items()}
        for key in ('grain_position','grain_scatter','grain_reverse','grain_length'):values[key]/=100
        return dict(values,grain_width=0.,granular=self.granular_button.isChecked(),grain_freeze=self.freeze.isChecked(),grain_seed=self.seed,
                    volume_curve=self.volume_curve,pitch_curve=self.pitch_curve)

    def reset(self):
        self.restore(Settings());self.select_view('eq')
        self.show_panel('sequence' if self.mode=='stitch' else None)

    def restore(self,s):
        for key,control in self.grains.items():
            value=getattr(s,key)
            if key in ('grain_position','grain_scatter','grain_width','grain_reverse','grain_length'):value*=100
            control.set_value(value)
        self.freeze.setChecked(s.grain_freeze);self.seed=s.grain_seed
        self.granular_button.setChecked(s.granular)
        self.volume_curve=tuple(tuple(p) for p in s.volume_curve)
        self.pitch_curve=tuple(tuple(p) for p in s.pitch_curve)

    def toggle_granular(self,enabled):
        # A lit button whose panel is covered opens that panel on the first click.
        if not enabled and not self.grain_panel.isVisible():
            enabled=True;self.granular_button.setChecked(True)
        self.show_panel('grains' if enabled else ('sequence' if self.mode=='stitch' else None))
        self.w.edited()

    def crossfade_clicked(self):
        if self.mode=='stitch' and not self.sequence_panel.isVisible():
            self.crossfade_button.setChecked(True);self.show_panel('sequence');return
        self.switch_mode(0 if self.mode=='stitch' else 1)

    def clear_workspace(self):
        w=self.w
        original=self.edit_audio or (self.items[0]['audio'] if self.items else None)
        return_to_source=self.mode=='stitch'
        self.mode='edit';self.crossfade_button.setChecked(False)
        self.items.clear();self.edit_audio=None;self.edit_session=None
        self.restoring=True;self.crossfade.setValue(80);self.curve.setCurrentIndex(0);self.restoring=False
        self.refresh_list();self.sequence_info.setText('Add clips from either folder, then arrange them.')
        self.show_panel(None);w.wave.sequence_markers=[]
        if return_to_source:
            w.stop();w.cancel_live()
            if original:w.install_audio(original,analyze(original.samples,original.rate))
            else:self.empty_sequence()

    def show_panel(self,name):
        self.grain_panel.setVisible(name=='grains' and self.granular_button.isChecked())
        if hasattr(self,'sequence_panel'):self.sequence_panel.setVisible(name=='sequence' and self.mode=='stitch')
        self.adapt_layout()

    def adapt_layout(self):
        if self.adapting:return
        self.adapting=True
        try:
            changed=False
            for name in ('grain','sequence'):
                if not hasattr(self,name+'_panel'):continue
                panel=getattr(self,name+'_panel');header=getattr(self,name+'_header')
                side=self.w.height()<900 and panel.isVisible()
                if side==getattr(self,name+'_sidebar'):continue
                changed=True;visible=panel.isVisible();setattr(self,name+'_sidebar',side);panel.hide()
                if side:
                    self.main.removeWidget(panel);panel.setMinimumWidth(210);panel.setMaximumWidth(260)
                    self.w.split.addWidget(panel)
                else:
                    self.main.insertWidget(1 if name=='grain' else 0,panel)
                    panel.setMinimumWidth(0);panel.setMaximumWidth(16777215)
                header.setDirection(QHBoxLayout.Direction.TopToBottom if side else QHBoxLayout.Direction.LeftToRight)
                header.itemAt(1 if name=='grain' else 5).spacerItem().changeSize(0,0,
                    QSizePolicy.Policy.Minimum if side else QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
                header.invalidate()
                if name=='grain':
                    for i,control in enumerate(self.grains.values()):
                        self.grain_grid.removeWidget(control);self.grain_grid.addWidget(control,i if side else i//4,0 if side else i%4)
                else:
                    self.sequence.setFlow(QListWidget.Flow.TopToBottom if side else QListWidget.Flow.LeftToRight)
                    self.sequence.setMinimumHeight(140 if side else 72);self.sequence.setMaximumHeight(16777215 if side else 72)
                    panel.layout().setStretch(1,1 if side else 0)
                    self.sequence_join.setDirection(QHBoxLayout.Direction.TopToBottom if side else QHBoxLayout.Direction.LeftToRight)
                panel.setVisible(visible)
            side=self.grain_sidebar or self.sequence_sidebar
            self.w.target.setVisible(not side)
            if changed and side:self.w.split.setSizes([180,900,0,230])
        finally:self.adapting=False

    def new_pattern(self):
        self.seed=secrets.randbelow(2**31);self.w.edited()

    def select_view(self,mode):
        self.w.wave.view_mode=mode
        for key,button in self.view_buttons.items():button.setChecked(key==mode)
        self.w.eq_strip.setVisible(mode=='eq');self.envelope_strip.setVisible(mode!='eq')
        if mode!='eq':self.sync_knobs()
        self.w.wave.update()

    def sync_knobs(self):
        mode=self.w.wave.view_mode
        if mode=='eq':return
        key='volume_curve' if mode=='volume' else 'pitch_curve'
        points=getattr(self,key)
        if len(points)!=5:
            times=np.linspace(0,1,5);points=tuple(zip(times,envelope_values(points,times)));setattr(self,key,points)
        self.restoring=True
        try:
            color='#ffbf7f' if mode=='volume' else '#bcadff'
            for i,(position,value,slider) in enumerate(self.envelope_knobs):
                position.setRange(0 if i==0 else points[i-1][0]*100+.1,100 if i==4 else points[i+1][0]*100-.1)
                position.setValue(points[i][0]*100);position.setEnabled(0<i<4)
                value.setRange(0 if mode=='volume' else -24,200 if mode=='volume' else 24)
                value.setDecimals(0 if mode=='volume' else 1);value.setSingleStep(1 if mode=='volume' else .1)
                value.setSuffix(' %' if mode=='volume' else ' st')
                value.setValue(points[i][1]*(100 if mode=='volume' else 1))
                slider.setRange(0 if mode=='volume' else -240,200 if mode=='volume' else 240)
                slider.setValue(round(points[i][1]*(100 if mode=='volume' else 10)))
                slider.setStyleSheet(f'QSlider::sub-page:horizontal {{background:{color};}} QSlider::handle:horizontal {{background:{color};}}')
        finally:self.restoring=False

    def knob_changed(self,index,kind,number):
        if self.restoring or self.w.wave.view_mode=='eq':return
        mode=self.w.wave.view_mode;key='volume_curve' if mode=='volume' else 'pitch_curve'
        points=list(getattr(self,key));t,value=points[index]
        if kind=='time':t=number/100
        else:value=number/(100 if mode=='volume' else (10 if kind=='slider' else 1))
        points[index]=(t,value);self.envelope_changed(key,tuple(points))

    def reset_point(self,index):
        mode=self.w.wave.view_mode;key='volume_curve' if mode=='volume' else 'pitch_curve'
        points=list(getattr(self,key));points[index]=(points[index][0],1. if mode=='volume' else 0.)
        self.envelope_changed(key,tuple(points))

    def reset_view(self):
        w=self.w;mode=w.wave.view_mode
        if mode=='eq':
            w.resetting=True
            for spin,freq,width,default in zip(w.eq_spins,w.eq_freqs,w.eq_widths,Settings().eq_frequencies):
                spin.setValue(0);freq.setValue(min(default,freq.maximum()));width.setValue(.85)
            w.resetting=False
        elif mode=='volume':self.volume_curve=Settings().volume_curve
        else:self.pitch_curve=Settings().pitch_curve
        self.sync_knobs()
        w.edited()

    def envelope_changed(self,key,points):
        setattr(self,key,points);self.sync_knobs();self.w.edited()

    def snapshot_edit(self):
        w=self.w
        return {'settings':asdict(w.current_settings()),'output_name':w.output_name.text(),
                'loop':w.loop.isChecked(),'play_original':w.play_original_check.isChecked(),
                'creative_view':w.wave.view_mode,
                'creative_panel':'grains' if self.grain_panel.isVisible() else ('sequence' if self.sequence_panel.isVisible() else None)}

    def choose_file(self,path):
        if self.mode=='edit':self.w.load(path)
        else:self.w.status.setText(f'{Path(path).name} selected. Add source / Add mix inserts it into the sequence.')

    def switch_mode(self,index):
        if self.restoring:return
        w=self.w
        if w.busy:
            self.crossfade_button.setChecked(self.mode=='stitch');return
        self.crossfade_button.setChecked(index==1)
        w.stop();w.cancel_live()
        if index==1:
            self.edit_audio=w.audio;self.edit_session=self.snapshot_edit() if w.audio else None
            self.mode='stitch';self.show_panel('sequence')
            if self.items:self.rebuild()
            else:self.empty_sequence()
        else:
            self.mode='edit';self.show_panel(None);w.wave.sequence_markers=[]
            if self.edit_audio:w.install_audio(self.edit_audio,analyze(self.edit_audio.samples,self.edit_audio.rate),self.edit_session)
            else:self.empty_sequence()

    def empty_sequence(self):
        w=self.w;w.audio=None;w.result=None;w.result_settings=None
        w.wave.source=None;w.wave.processed=None;w.wave.sequence_markers=[];w.wave.clear_playback()
        w.clip_title.setText('Add clips to the sequence' if self.mode=='stitch' else 'Choose a sound')
        w.metadata.setText('');w.update_enabled()

    def add_selected(self,pane):
        item=pane.list.currentItem()
        if not pane.isVisible() or item is None:
            selected,_=QFileDialog.getOpenFileName(self.w,'Add WAV to sequence',str(pane.folder),'WAV audio (*.wav)')
            if not selected:return
            path=Path(selected)
        else:path=Path(item.data(Qt.ItemDataRole.UserRole))
        self.w.job(lambda cancel,progress:load_audio(path,cancel),lambda audio:self.append(audio,Settings()),stop_playback=False)

    def add_edit(self):
        if self.edit_audio is None:
            self.w.status.setText('Load and shape a sound in Edit sound first.');return
        self.append(self.edit_audio,Settings(**self.edit_session['settings']))

    def append(self,audio,settings):
        if len(self.items)>=32:
            self.w.show_error('A sequence supports up to 32 clips.');return
        if sum(item['audio'].samples.nbytes for item in self.items)+audio.samples.nbytes>256*1024*1024:
            self.w.show_error('Sequence sources exceed 256 MB. Use shorter clips.');return
        self.items.append({'audio':audio,'settings':settings,'fade':80.,'curve':'Equal gain','cache':RenderCache(max_bytes=16*1024*1024)})
        self.refresh_list(len(self.items)-1);self.rebuild()

    def refresh_list(self,selected=0):
        self.sequence.blockSignals(True);self.sequence.clear()
        for i,item in enumerate(self.items):
            entry=QListWidgetItem(f'{i+1:02d}  {item["audio"].path.stem}\n'+('Start' if i==0 else f'↔ {item["fade"]:g} ms · {item["curve"]}'))
            entry.setSizeHint(QSize(190,48));self.sequence.addItem(entry)
        self.sequence.setCurrentRow(min(selected,len(self.items)-1));self.sequence.blockSignals(False)
        self.select_join(self.sequence.currentRow())

    def select_join(self,index):
        self.crossfade.setEnabled(index>0);self.curve.setEnabled(index>0)
        self.join_reset.setEnabled(index>0)
        if index<0:return
        self.restoring=True
        self.crossfade.setValue(self.items[index]['fade']);self.curve.setCurrentText(self.items[index]['curve'])
        self.restoring=False

    def reset_join(self):
        index=self.sequence.currentRow()
        if index<=0:return
        self.restoring=True;self.crossfade.setValue(80);self.curve.setCurrentIndex(0);self.restoring=False
        self.join_changed()

    def join_changed(self,*args):
        if self.restoring or self.w.busy:return
        index=self.sequence.currentRow()
        if index<=0:return
        self.items[index]['fade']=self.crossfade.value();self.items[index]['curve']=self.curve.currentText()
        self.refresh_list(index);self.rebuild()

    def move(self,direction):
        i=self.sequence.currentRow();j=i+direction
        if i<0 or not 0<=j<len(self.items):return
        self.items[i],self.items[j]=self.items[j],self.items[i]
        self.refresh_list(j);self.rebuild()

    def remove(self):
        i=self.sequence.currentRow()
        if i<0:return
        self.items.pop(i);self.refresh_list(max(0,i-1));self.rebuild()

    def rebuild(self,restore_session=None):
        w=self.w
        if not self.items:
            w.stop();w.cancel_live();self.empty_sequence();return
        items=list(self.items)
        previous_duration=w.audio.duration if w.audio and w.audio.assembly else None
        session=copy.deepcopy(restore_session or (self.snapshot_edit() if previous_duration else None))
        def work(cancel,progress):
            clips=[];provenance=[];sources=[]
            for item in items:
                check_cancel(cancel);audio=item['audio']
                settings=replace(item['settings'],subtype='FLOAT')
                result=render(audio,settings,cancel,progress,cache=item['cache'])
                clips.append((result[0],result[1],audio));sources.extend(audio.sources or ((str(audio.path),audio.sha256),))
                provenance.append({'path':str(audio.path),'sha256':audio.sha256,'settings':asdict(settings)})
            joins=[(item['fade'],item['curve']) for item in items[1:]]
            samples,rate,markers=stitch_clips(clips,joins,cancel)
            base=items[0]['audio']
            audio=Audio(base.path,samples,rate,'FLOAT',base.sha256,tuple(dict.fromkeys(sources)),
                        {'clips':provenance,'joins':joins,'markers':markers})
            return audio,analyze(samples,rate)
        def done(value):
            audio,analysis=value
            if session and restore_session is None:
                settings=session['settings']
                settings['start']=min(settings['start'],audio.duration)
                end=settings['end']
                settings['end']=audio.duration if end is None or end==previous_duration else min(end,audio.duration)
            w.install_audio(audio,analysis,session)
            w.wave.sequence_markers=audio.assembly['markers'];w.wave.update()
            if not session:w.output_name.setText('sequence_mix')
            self.sequence_info.setText(f'{len(items)} clips · {audio.duration:.2f}s · overlap shown on waveform')
            w.status.setText('Sequence ready. Crossfades are capped at half of each neighbouring clip.')
        w.job(work,done,stop_playback=False)

    def rename_selected(self,pane,new_name=None):
        w=self.w
        if w.busy or w.live_worker:
            w.status.setText('Wait for the current render, then rename the selected clip.');return
        item=pane.list.currentItem()
        if item is None:return
        path=Path(item.data(Qt.ItemDataRole.UserRole))
        if new_name is None:
            new_name,ok=QInputDialog.getText(w,'Rename WAV','New filename (without .wav)',text=path.stem)
            if not ok:return
        try:new_path=rename_wav(path,new_name)
        except (OSError,ValueError) as error:w.show_error(str(error));return
        for audio in [w.audio,self.edit_audio]+[item['audio'] for item in self.items]:
            if audio is None:continue
            if audio.path==path:audio.path=new_path
            if audio.sources:audio.sources=tuple((str(new_path) if p==str(path) else p,d) for p,d in audio.sources)
            if audio.assembly:
                for clip in audio.assembly['clips']:
                    if clip['path']==str(path):clip['path']=str(new_path)
        if w.audio and w.audio.path==new_path and not w.audio.assembly:w.clip_title.setText(new_path.name)
        if w.output_name.text()==path.stem+'_mix':w.output_name.setText(new_path.stem+'_mix')
        pane.refresh();self.refresh_list(self.sequence.currentRow())
        for i in range(pane.list.count()):
            if pane.list.item(i).data(Qt.ItemDataRole.UserRole)==str(new_path):
                pane.list.blockSignals(True);pane.list.setCurrentRow(i);pane.list.blockSignals(False);break
        w.status.setText(f'Renamed to {new_path.name}. Audio samples and current settings are unchanged.')

    def session_fields(self):
        return {'creative_view':self.w.wave.view_mode,'studio_mode':self.mode,
                'creative_panel':'grains' if self.grain_panel.isVisible() else ('sequence' if self.sequence_panel.isVisible() else None),
                'sequence':[{'path':str(item['audio'].path),'settings':asdict(item['settings']),
                             'fade':item['fade'],'curve':item['curve']} for item in self.items],
                'edit_path':str(self.edit_audio.path) if self.edit_audio else None,'edit_session':self.edit_session}

    def restore_session(self,session):
        self.select_view(session.get('creative_view','eq'))
        self.show_panel(session.get('creative_panel','grains' if self.granular_button.isChecked() else ('sequence' if self.mode=='stitch' else None)))

    def restore_workspace(self,session):
        w=self.w
        def work(cancel,progress):
            items=[]
            for item in session.get('sequence',[]):
                items.append({**item,'audio':load_audio(item['path'],cancel),'settings':Settings(**item['settings']),
                              'cache':RenderCache(max_bytes=16*1024*1024)})
            edit=load_audio(session['edit_path'],cancel) if session.get('edit_path') else None
            return items,edit
        def done(value):
            self.items,self.edit_audio=value;self.edit_session=session.get('edit_session')
            self.refresh_list()
            if session.get('studio_mode')=='stitch':
                self.crossfade_button.setChecked(True)
                self.mode='stitch';self.show_panel('sequence');self.rebuild(session)
            elif session.get('audio'):w.load(Path(session['audio']),session)
        w.job(work,done)
