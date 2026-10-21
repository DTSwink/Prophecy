"""Lafan Cutter: native desktop motion curation. No training or Unreal dependency."""
from __future__ import annotations

import argparse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
import math
import os
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import traceback

import numpy as np
from OpenGL import GL, GLU
from PIL import Image, ImageTk
from pyopengltk import OpenGLFrame

from motion import read_motion, clip_record, save_dataset, load_dataset, atomic_json

HERE = Path(__file__).resolve().parent
DATA = Path.home() / 'Documents' / 'Lafan Cutter'
SOURCES = {'LAFAN Re-solved · 60 fps': Path.home() / 'Downloads' / 'LAFAN-Re-solved',
           'LAFAN1 original · 30 fps': Path.home() / 'Downloads' / 'LaFAN1'}
APP_ID = 'Prophecy.LafanCutter.Desktop.1'
BG, PANEL, FIELD = '#10151c', '#19212b', '#222d3a'
TEXT, MUTED, LINE, ACCENT = '#edf2f8', '#9cacbd', '#344353', '#ffa75a'


class Viewport(OpenGLFrame):
    def __init__(self, parent, app):
        self.app = app
        super().__init__(parent, bg=BG, highlightthickness=0)

    def initgl(self):
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_LINE_SMOOTH)
        GL.glEnable(GL.GL_POINT_SMOOTH)

    def redraw(self):
        self.app.render()


class Cutter(tk.Tk):
    def __init__(self, data_dir=DATA, smoke=False):
        if os.name == 'nt':
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        super().__init__()
        self.withdraw()
        self.title('Lafan Cutter')
        self.configure(bg=BG)
        self.minsize(1120, 700)
        self.geometry('1500x880+30+35')
        self.data_dir = Path(data_dir)
        self.dataset_root = self.data_dir / 'datasets'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.cache = OrderedDict()
        self.request_id = 0
        self.motion = None
        self.clips = []
        self.frame = self.start = self.end = 0
        self.playing = False
        self.from_source = True
        self.yaw, self.pitch, self.distance = -.6, .2, 4.3
        self.target = np.array([0., 1., 0.])
        self.mouse = None
        self.drag = None
        self.dirty = False
        self.busy_save = False
        self.last_tick = time.perf_counter()
        self.accumulator = 0.
        self.smoke = smoke
        self.last_error = None
        self.iconbitmap(default=str(HERE / 'icon.ico'))
        self.icon_photo = ImageTk.PhotoImage(Image.open(HERE / 'icon.png'))
        self.iconphoto(True, self.icon_photo)
        self.configure_style()
        self.source_var = tk.StringVar(value=next(iter(SOURCES)))
        self.source_dir = SOURCES[self.source_var.get()]
        self.filter_var = tk.StringVar()
        self.name_var = tk.StringVar(value='My dataset')
        self.start_var, self.end_var = tk.StringVar(value='0'), tk.StringVar(value='0')
        self.follow_var = tk.BooleanVar(value=True)
        self.loop_var = tk.BooleanVar(value=True)
        self.speed_var = tk.StringVar(value='1×')
        self.status_var = tk.StringVar(value='Select a motion on the left to begin.')
        self.build_layout()
        self.filter_var.trace_add('write', lambda *_: self.populate_source())
        self.name_var.trace_add('write', lambda *_: self.changed())
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<space>', lambda e: self.key_action(e, self.toggle))
        self.bind('<Left>', lambda e: self.key_action(e, lambda: self.step(-1)))
        self.bind('<Right>', lambda e: self.key_action(e, lambda: self.step(1)))
        self.bind('<Key-i>', lambda e: self.key_action(e, lambda: self.mark('start')))
        self.bind('<Key-o>', lambda e: self.key_action(e, lambda: self.mark('end')))
        self.bind('<Control-s>', lambda e: self.save())
        self.bind('<Control-Return>', lambda e: self.add_cut())
        self.restore_draft()
        self.scan_source()
        self.refresh_clips()
        self.deiconify()
        if not smoke:
            self.state('zoomed')
        self.after(20, self.tick)
        self.after(1500, self.autosave)
        self.after(400, self.restore_motion)
        self.after(200,self.record_identity)

    def record_identity(self):
        if os.name!='nt':return
        from ctypes import wintypes
        shell=ctypes.windll.shell32
        pointer=ctypes.c_void_p()
        result=shell.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(pointer))
        actual=ctypes.wstring_at(pointer) if result==0 and pointer.value else None
        if pointer.value:
            ctypes.windll.ole32.CoTaskMemFree.argtypes=[ctypes.c_void_p]
            ctypes.windll.ole32.CoTaskMemFree(pointer)
        user=ctypes.windll.user32
        user.GetParent.argtypes=[wintypes.HWND];user.GetParent.restype=wintypes.HWND
        hwnd=user.GetParent(self.winfo_id())
        user.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        user.SendMessageW.restype=ctypes.c_ssize_t
        # Set icons on the actual native top-level HWND too. Tk's class-icon
        # fallback alone does not consistently supply taskbar icons on Windows.
        user.LoadImageW.argtypes=[wintypes.HINSTANCE,wintypes.LPCWSTR,wintypes.UINT,
                                 ctypes.c_int,ctypes.c_int,wintypes.UINT]
        user.LoadImageW.restype=wintypes.HANDLE
        self.native_icons=[user.LoadImageW(None,str(HERE/'icon.ico'),1,size,size,0x10) for size in (32,64)]
        for kind,handle in enumerate(self.native_icons):
            if not handle:raise OSError('Could not load Lafan Cutter taskbar icon')
            user.SendMessageW(hwnd,0x80,kind,handle)
        small=user.SendMessageW(hwnd,0x7f,0,0)
        large=user.SendMessageW(hwnd,0x7f,1,0)
        atomic_json(self.data_dir/'app-identity.json',dict(pid=os.getpid(),app_id=actual,
             window=int(hwnd),small_icon=int(small),large_icon=int(large),icon_file=str(HERE/'icon.ico')))

    def configure_style(self):
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('.', background=PANEL, foreground=TEXT, fieldbackground=FIELD,
                        bordercolor=LINE, font=('Segoe UI', 10), focuscolor=ACCENT)
        style.configure('TFrame', background=PANEL)
        style.configure('TLabel', background=PANEL, foreground=TEXT)
        style.configure('Muted.TLabel', foreground=MUTED)
        style.configure('Heading.TLabel', font=('Segoe UI', 12, 'bold'))
        style.configure('TButton', background=FIELD, foreground=TEXT, padding=(9, 6), borderwidth=0)
        style.map('TButton', background=[('active', '#38485b'), ('disabled', PANEL)], foreground=[('disabled', '#667587')])
        style.configure('TEntry', padding=6, insertcolor=TEXT)
        style.configure('Treeview', background=BG, fieldbackground=BG, foreground=TEXT,
                        rowheight=29, borderwidth=0)
        style.map('Treeview', background=[('selected', '#51402e')], foreground=[('selected', '#fff1df')])
        style.configure('Treeview.Heading', background=FIELD, foreground=MUTED, padding=(5,7))
        style.configure('TCombobox', padding=5, arrowcolor=TEXT)
        style.map('TCombobox', fieldbackground=[('readonly',FIELD)], foreground=[('readonly',TEXT)])
        style.configure('TCheckbutton', background=PANEL)

    def button(self, parent, text, command, **kw):
        return ttk.Button(parent, text=text, command=command, **kw)

    def build_layout(self):
        header = ttk.Frame(self, padding=(18, 12)); header.pack(fill='x')
        self.brand_icon = ImageTk.PhotoImage(Image.open(HERE / 'icon.png').resize((38,38)))
        ttk.Label(header, image=self.brand_icon).pack(side='left', padx=(0,10))
        ttk.Label(header, text='LAFAN CUTTER', font=('Segoe UI', 17, 'bold')).pack(side='left')
        ttk.Label(header, text='Select. Trim. Collect.', style='Muted.TLabel').pack(side='left', padx=20)
        self.button(header, 'Open datasets folder', self.open_folder).pack(side='right')
        body = tk.PanedWindow(self, orient='horizontal', bg=LINE, sashwidth=5, bd=0)
        body.pack(fill='both', expand=True, padx=12, pady=(0,8))
        left = ttk.Frame(body, padding=12)
        centre = ttk.Frame(body)
        right = ttk.Frame(body, padding=12)
        body.add(left, minsize=230, width=280)
        body.add(centre, minsize=470, stretch='always')
        body.add(right, minsize=290, width=350)
        ttk.Label(left, text='SOURCE MOTIONS', style='Heading.TLabel').pack(anchor='w', pady=(0,10))
        self.source_combo = ttk.Combobox(left, textvariable=self.source_var, values=list(SOURCES), state='readonly')
        self.source_combo.pack(fill='x')
        self.source_combo.bind('<<ComboboxSelected>>', lambda _: self.change_source())
        source_buttons = ttk.Frame(left); source_buttons.pack(fill='x', pady=7)
        self.button(source_buttons, 'Folder…', self.choose_source).pack(side='left')
        self.button(source_buttons, 'Refresh', self.scan_source).pack(side='right')
        ttk.Label(left, text='Filter motions', style='Muted.TLabel').pack(anchor='w')
        ttk.Entry(left, textvariable=self.filter_var).pack(fill='x', pady=(4,8))
        self.source_tree = self.tree(left, [('motion','Motion',210)])
        self.source_tree.bind('<<TreeviewSelect>>', self.select_source)
        self.source_count = ttk.Label(left, text='', style='Muted.TLabel')
        self.source_count.pack(anchor='w', pady=(8,0))
        self.source_hint = ttk.Label(left, text='', style='Muted.TLabel', wraplength=240)
        self.source_hint.pack(anchor='w', pady=(6,0))

        top = ttk.Frame(centre, padding=(12,8)); top.pack(fill='x')
        self.title_var = tk.StringVar(value='Choose a motion')
        ttk.Label(top, textvariable=self.title_var, font=('Segoe UI',11,'bold')).pack(side='left')
        self.button(top, 'Fit view', self.fit_view).pack(side='right')
        self.viewport = Viewport(centre, self)
        self.viewport.pack(fill='both', expand=True)
        self.viewport.bind('<ButtonPress-1>', self.mouse_down)
        self.viewport.bind('<B1-Motion>', self.orbit)
        self.viewport.bind('<ButtonPress-3>', self.mouse_down)
        self.viewport.bind('<B3-Motion>', self.pan)
        self.viewport.bind('<MouseWheel>', self.zoom)
        self.viewport.bind('<Configure>', lambda _: self.draw())
        controls = ttk.Frame(centre, padding=(12,10)); controls.pack(fill='x')
        self.info_var = tk.StringVar(value='Orbit: drag  ·  Pan: right-drag  ·  Zoom: scroll')
        ttk.Label(controls, textvariable=self.info_var, style='Muted.TLabel').pack(anchor='w', pady=(0,7))
        self.timeline = tk.Canvas(controls, height=78, bg=BG, highlightthickness=0, cursor='hand2')
        self.timeline.pack(fill='x')
        self.timeline.bind('<Configure>', lambda _: self.draw_timeline())
        self.timeline.bind('<ButtonPress-1>', self.timeline_down)
        self.timeline.bind('<B1-Motion>', self.timeline_move)
        self.timeline.bind('<ButtonRelease-1>', self.timeline_up)
        ranges = ttk.Frame(controls); ranges.pack(fill='x', pady=8)
        for label, variable, which in [('In', self.start_var,'start'), ('Out', self.end_var,'end')]:
            ttk.Label(ranges, text=label).pack(side='left', padx=(0,5))
            spin = ttk.Spinbox(ranges, from_=0, to=9999999, width=7, textvariable=variable,
                               command=self.apply_range)
            spin.pack(side='left', padx=(0,7))
            spin.bind('<Return>', lambda _: self.apply_range())
            spin.bind('<FocusOut>', lambda _: self.apply_range())
            self.button(ranges, 'Set '+label, lambda w=which: self.mark(w)).pack(side='left', padx=(0,8))
        self.button(ranges, 'Full clip', self.full_range).pack(side='right')
        playback = ttk.Frame(controls); playback.pack(fill='x')
        self.button(playback, '◀', lambda: self.step(-1), width=3).pack(side='left')
        self.play_button = self.button(playback, 'Play', self.toggle, width=7)
        self.play_button.pack(side='left', padx=4)
        self.button(playback, '▶', lambda: self.step(1), width=3).pack(side='left')
        speed = ttk.Combobox(playback, textvariable=self.speed_var, values=['0.25×','0.5×','1×','2×'], width=5, state='readonly')
        speed.pack(side='left', padx=8)
        ttk.Checkbutton(playback, text='Loop trim', variable=self.loop_var).pack(side='left')
        ttk.Checkbutton(playback, text='Follow pelvis', variable=self.follow_var, command=self.draw).pack(side='right')
        self.add_button = tk.Button(controls, text='ADD TRIM TO DATASET  →', bg=ACCENT, fg='#21170d',
                   activebackground='#ffc48c', relief='flat', font=('Segoe UI',11,'bold'),
                   pady=10, command=self.add_cut)
        self.add_button.pack(fill='x', pady=(12,0))

        ttk.Label(right, text='YOUR DATASET', style='Heading.TLabel').pack(anchor='w', pady=(0,10))
        ttk.Label(right, text='Dataset name', style='Muted.TLabel').pack(anchor='w')
        ttk.Entry(right, textvariable=self.name_var).pack(fill='x', pady=(4,7))
        actions = ttk.Frame(right); actions.pack(fill='x', pady=(0,10))
        self.button(actions, 'New', self.new_dataset).pack(side='left')
        self.button(actions, 'Open…', self.open_dataset).pack(side='left', padx=5)
        self.save_button = self.button(actions, 'Save dataset', self.save)
        self.save_button.pack(side='right')
        self.cut_tree = self.tree(right, [('clip','Selected trims',210),('length','Seconds',65)])
        self.cut_tree.bind('<<TreeviewSelect>>', self.select_cut)
        edit = ttk.Frame(right); edit.pack(fill='x', pady=8)
        self.button(edit, '↑', lambda: self.move_cut(-1), width=3).pack(side='left')
        self.button(edit, '↓', lambda: self.move_cut(1), width=3).pack(side='left', padx=5)
        self.button(edit, 'Remove trim', self.remove_cut).pack(side='right')
        self.summary_var = tk.StringVar(value='0 trims')
        ttk.Label(right, textvariable=self.summary_var, style='Heading.TLabel').pack(anchor='w', pady=8)
        self.saved_var = tk.StringVar(value='Draft is recovered automatically.\nSave dataset exports your BVH cuts.')
        ttk.Label(right, textvariable=self.saved_var, style='Muted.TLabel', wraplength=300).pack(anchor='w')
        ttk.Label(self, textvariable=self.status_var, padding=(16,7), style='Muted.TLabel').pack(fill='x')

    def tree(self, parent, columns):
        frame = ttk.Frame(parent); frame.pack(fill='both', expand=True)
        tree = ttk.Treeview(frame, columns=[x[0] for x in columns], show='headings', selectmode='browse')
        for key, label, width in columns:
            tree.heading(key, text=label); tree.column(key, width=width, minwidth=45, stretch=key!='length')
        scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y'); tree.pack(side='left', fill='both', expand=True)
        horizontal = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
        tree.configure(xscrollcommand=horizontal.set); horizontal.pack(fill='x')
        return tree

    def report_callback_exception(self, exc, value, tb):
        self.last_error = ''.join(traceback.format_exception(exc,value,tb))
        (self.data_dir/'error.log').write_text(self.last_error, encoding='utf-8')
        self.status_var.set('Error: '+str(value))
        if not self.smoke: messagebox.showerror('Lafan Cutter', str(value), parent=self)

    def key_action(self, event, fn):
        if isinstance(event.widget,(ttk.Entry,ttk.Spinbox,ttk.Combobox,tk.Entry)):
            return None
        fn(); return 'break'

    def change_source(self):
        self.source_dir = SOURCES[self.source_var.get()]
        self.filter_var.set(''); self.scan_source()

    def choose_source(self):
        folder = filedialog.askdirectory(parent=self, title='Select a folder containing BVH motions')
        if folder:
            self.source_dir = Path(folder)
            self.source_var.set('Custom BVH folder')
            self.scan_source()

    def scan_source(self):
        self.paths = sorted(self.source_dir.rglob('*.bvh')) if self.source_dir.exists() else []
        self.populate_source()
        self.source_hint.configure(text='Original motion and timing are preserved.' if self.paths else
                                   'No BVH files here yet. Choose Folder or Refresh after the download finishes.')

    def populate_source(self):
        if not hasattr(self,'paths'): return
        query = self.filter_var.get().casefold()
        selected = self.source_tree.selection()
        self.source_tree.delete(*self.source_tree.get_children())
        for n,path in enumerate(self.paths):
            if query in path.stem.casefold():
                self.source_tree.insert('', 'end', iid=str(n), values=(path.stem,))
        if selected and self.source_tree.exists(selected[0]): self.source_tree.selection_set(selected)
        self.source_count.configure(text=f'{len(self.source_tree.get_children())} / {len(self.paths)} motions')

    def select_source(self, _=None):
        selection=self.source_tree.selection()
        if selection: self.load(self.paths[int(selection[0])], True)

    def select_cut(self, _=None):
        selection=self.cut_tree.selection()
        if selection:
            clip=self.clips[int(selection[0])]
            self.load(Path(clip['source']), False, (clip['start'],clip['end']), clip['label'])

    def cached_motion(self,path):
        key=str(path.resolve())
        stamp=(path.stat().st_size,path.stat().st_mtime_ns)
        if key in self.cache and self.cache[key][0]==stamp:
            self.cache.move_to_end(key); return self.cache[key][1]
        motion=read_motion(path)
        self.cache[key]=(stamp,motion)
        while len(self.cache)>2: self.cache.popitem(last=False)
        return motion

    def load(self,path,source=True,bounds=None,label=None,resume_frame=None):
        self.request_id+=1; request=self.request_id
        self.playing=False; self.play_button.configure(text='Play')
        self.add_button.configure(state='disabled')
        self.status_var.set('Loading '+path.name+'…')
        future=self.executor.submit(self.cached_motion,path)
        def finish():
            if request!=self.request_id: return
            if not future.done(): self.after(30,finish); return
            try:
                motion=future.result()
                self.motion=motion; self.from_source=source
                self.start,self.end=bounds or (0,motion.count-1)
                if not 0<=self.start<=self.end<motion.count: raise ValueError('Saved range is no longer available')
                self.frame=self.start if resume_frame is None else max(0,min(motion.count-1,resume_frame))
                self.title_var.set(label or path.stem)
                self.add_button.configure(state='normal' if source else 'disabled')
                self.fit_view(); self.update_controls()
                self.status_var.set(f'{motion.count:,} frames · {motion.fps:.2f} fps · '+('Source preview' if source else 'Dataset trim preview'))
            except Exception as e:
                self.status_var.set('Could not load: '+str(e))
                if not self.smoke: messagebox.showerror('Motion could not be loaded',str(e),parent=self)
        self.after(30,finish)

    def update_controls(self):
        self.start_var.set(str(self.start));self.end_var.set(str(self.end))
        if self.motion:
            count=self.end-self.start+1
            self.info_var.set(f'Frame {self.frame:,} / {self.motion.count-1:,}   ·   Trim {self.start:,}–{self.end:,}   ·   {count:,} frames / {count/self.motion.fps:.2f}s')
        self.draw_timeline();self.draw()

    def apply_range(self):
        if not self.motion:return
        try:
            start,end=int(self.start_var.get()),int(self.end_var.get())
            if not 0<=start<=end<self.motion.count:raise ValueError()
        except ValueError:
            self.status_var.set('Use frame numbers with 0 ≤ In ≤ Out < frame count.');self.update_controls();return
        self.start,self.end=start,end;self.frame=max(start,min(self.frame,end));self.update_controls()

    def mark(self,which):
        if not self.motion:return
        if which=='start':self.start=min(self.frame,self.end)
        else:self.end=max(self.frame,self.start)
        self.update_controls()

    def full_range(self):
        if self.motion:self.start,self.end=0,self.motion.count-1;self.update_controls()

    def step(self,delta):
        if not self.motion:return
        self.playing=False;self.play_button.configure(text='Play')
        self.frame=max(0,min(self.motion.count-1,self.frame+delta));self.update_controls()

    def toggle(self):
        if not self.motion:return
        self.playing=not self.playing;self.last_tick=time.perf_counter();self.accumulator=0
        if self.loop_var.get() and not self.start<=self.frame<=self.end:self.frame=self.start
        self.play_button.configure(text='Pause' if self.playing else 'Play')

    def tick(self):
        now=time.perf_counter();dt=min(.15,now-self.last_tick);self.last_tick=now
        if self.playing and self.motion:
            self.accumulator+=dt*self.motion.fps*float(self.speed_var.get().rstrip('×'))
            steps=int(self.accumulator);self.accumulator-=steps
            if steps:
                lo,hi=(self.start,self.end) if self.loop_var.get() else (0,self.motion.count-1)
                self.frame=lo+(self.frame-lo+steps)%(hi-lo+1)
                self.update_controls()
        self.after(16,self.tick)

    def timeline_x(self,frame):
        return 18+frame/max(1,self.motion.count-1)*(max(40,self.timeline.winfo_width())-36)

    def timeline_frame(self,x):
        return max(0,min(self.motion.count-1,round((x-18)/max(1,self.timeline.winfo_width()-36)*(self.motion.count-1))))

    def draw_timeline(self):
        t=self.timeline;t.delete('all');w=t.winfo_width()
        if not self.motion:
            t.create_text(w/2,39,text='Select a motion to choose a trim',fill=MUTED);return
        a,b=self.timeline_x(self.start),self.timeline_x(self.end)
        t.create_line(18,29,w-18,29,fill=LINE,width=10)
        t.create_rectangle(a,14,b,40,fill='#62472d',outline='')
        t.create_line(a,29,b,29,fill=ACCENT,width=6)
        for x,label in [(a,'IN'),(b,'OUT')]:
            t.create_rectangle(x-5,13,x+5,43,fill=ACCENT,outline='')
            t.create_text(x,7,text=label,fill=ACCENT,font=('Segoe UI',8))
        if b-a>65:t.create_text((a+b)/2,27,text='↔ move trim',fill='#21170d',font=('Segoe UI',8,'bold'))
        t.create_line(18,60,w-18,60,fill=LINE,width=3)
        x=self.timeline_x(self.frame)
        t.create_line(x,47,x,72,fill=TEXT,width=2)
        t.create_oval(x-4,56,x+4,64,fill=TEXT,outline='')

    def timeline_down(self,e):
        if not self.motion:return
        self.playing=False;self.play_button.configure(text='Play')
        a,b=self.timeline_x(self.start),self.timeline_x(self.end)
        if e.y<46 and min(abs(e.x-a),abs(e.x-b))<12:
            self.drag='start' if abs(e.x-a)<abs(e.x-b) or (a==b and e.x<a) else 'end'
        elif e.y<46 and a<e.x<b:self.drag='window';self.drag_offset=self.timeline_frame(e.x)-self.start
        else:self.drag='scrub'
        self.timeline_move(e)

    def timeline_move(self,e):
        if not self.motion or not self.drag:return
        f=self.timeline_frame(e.x)
        if self.drag=='start':self.start=min(f,self.end);self.frame=self.start
        elif self.drag=='end':self.end=max(f,self.start);self.frame=self.end
        elif self.drag=='window':
            length=self.end-self.start
            self.start=max(0,min(self.motion.count-1-length,f-self.drag_offset));self.end=self.start+length;self.frame=self.start
        else:self.frame=f
        self.update_controls()

    def timeline_up(self,e):
        self.timeline_move(e);self.drag=None

    def add_cut(self):
        if not self.motion or not self.from_source or str(self.add_button['state'])=='disabled':return
        self.apply_range()
        self.clips.append(clip_record(self.motion,self.start,self.end))
        self.changed();self.refresh_clips()
        self.status_var.set(f'Added {self.end-self.start+1:,} frames to the dataset. Select another range or motion.')

    def refresh_clips(self):
        self.cut_tree.delete(*self.cut_tree.get_children())
        for i,row in enumerate(self.clips):
            self.cut_tree.insert('','end',iid=str(i),values=(row['label'],f"{row['frames']/row['fps']:.2f}"))
        seconds=sum(c['frames']/c['fps'] for c in self.clips)
        self.summary_var.set(f'{len(self.clips)} trims  ·  {seconds:.2f} seconds')

    def remove_cut(self):
        ids=self.cut_tree.selection()
        if ids:
            self.clips.pop(int(ids[0]));self.changed();self.refresh_clips()
            self.status_var.set('Removed from this draft. Saved datasets and source motions are preserved.')

    def move_cut(self,direction):
        ids=self.cut_tree.selection()
        if not ids:return
        i=int(ids[0]);j=i+direction
        if 0<=j<len(self.clips):
            self.clips[i],self.clips[j]=self.clips[j],self.clips[i]
            self.changed();self.refresh_clips();self.cut_tree.selection_set(str(j))

    def changed(self):
        self.dirty=True
        if hasattr(self,'saved_var'):self.saved_var.set('Unsaved changes · draft recovered automatically')

    def save(self):
        if self.busy_save:return
        name=self.name_var.get();clips=json.loads(json.dumps(self.clips))
        self.busy_save=True;self.save_button.configure(state='disabled')
        self.status_var.set('Saving BVH cuts…')
        future=self.executor.submit(save_dataset,self.dataset_root,name,clips)
        def finish():
            if not future.done():self.after(50,finish);return
            self.busy_save=False;self.save_button.configure(state='normal')
            try:
                dest=future.result()
                unchanged=self.clips==clips and self.name_var.get()==name
                self.dirty=not unchanged
                self.saved_var.set(f'Saved: {name}\n'+('All current trims saved.' if unchanged else 'Newer edits remain unsaved.'))
                self.status_var.set('Saved dataset: '+str(dest))
                self.write_draft()
            except Exception as e:
                self.status_var.set('Save failed: '+str(e))
                if not self.smoke:messagebox.showerror('Dataset not saved',str(e),parent=self)
        self.after(50,finish)

    def keep_draft(self):
        if self.busy_save:
            self.status_var.set('Wait for the current save to finish.');return False
        # Archive every replaced draft; switching never destroys unsaved curation.
        if self.clips and self.dirty:
            atomic_json(self.data_dir/'drafts'/f'draft_{time.time_ns()}.json',self.draft())
        return True

    def new_dataset(self):
        if not self.keep_draft():return
        self.clips=[];self.name_var.set('My dataset');self.changed();self.refresh_clips()
        self.status_var.set('New dataset. Previous unsaved drafts are kept in the drafts folder.')
        self.write_draft()

    def open_dataset(self):
        if not self.keep_draft():return
        self.dataset_root.mkdir(parents=True,exist_ok=True)
        path=filedialog.askopenfilename(parent=self,initialdir=str(self.dataset_root),
             title='Open a saved dataset.json (or an archived draft)',filetypes=[('Dataset or draft','*.json')])
        if not path:return
        try:
            doc=json.loads(Path(path).read_text(encoding='utf-8'))
            if doc.get('format')=='lafan-cutter-draft':
                name,clips=doc['name'],doc['clips']
            else:name,clips=load_dataset(path)
            self.clips=clips;self.name_var.set(name);self.dirty=doc.get('format')=='lafan-cutter-draft'
            self.refresh_clips();self.saved_var.set('Opened: '+name);self.write_draft()
        except Exception as e:messagebox.showerror('Cannot open dataset',str(e),parent=self)

    def open_folder(self):
        self.dataset_root.mkdir(parents=True,exist_ok=True)
        os.startfile(str(self.dataset_root))

    def draft(self):
        return dict(format='lafan-cutter-draft',name=self.name_var.get(),clips=self.clips,dirty=self.dirty,
            source_dir=str(self.source_dir),source_label=self.source_var.get(),
            preview=dict(path=str(self.motion.path),source=self.from_source,start=self.start,end=self.end,frame=self.frame) if self.motion else None)

    def write_draft(self):
        atomic_json(self.data_dir/'session.json',self.draft())

    def autosave(self):
        try:self.write_draft()
        except OSError as e:self.status_var.set('Draft recovery could not be saved: '+str(e))
        self.after(1500,self.autosave)

    def restore_draft(self):
        self.resume_preview=None
        path=self.data_dir/'session.json'
        if path.exists():
            try:
                d=json.loads(path.read_text(encoding='utf-8'))
                self.clips=d['clips'];self.name_var.set(d['name']);self.dirty=d.get('dirty',True)
                self.source_dir=Path(d['source_dir']);self.source_var.set(d['source_label'])
                self.resume_preview=d.get('preview')
                self.saved_var.set('Recovered last session'+(' · unsaved changes' if self.dirty else ''))
            except (OSError,ValueError,KeyError) as e:self.status_var.set('Could not restore previous session: '+str(e))

    def restore_motion(self):
        p=self.resume_preview
        if p and Path(p['path']).is_file():self.load(Path(p['path']),p['source'],(p['start'],p['end']),resume_frame=p.get('frame'))
        elif self.paths:
            index=next((i for i,p in enumerate(self.paths) if p.name.lower()=='walk1_subject1.bvh'),0)
            self.source_tree.selection_set(str(index));self.source_tree.see(str(index))

    def fit_view(self):
        if self.motion:
            pose=self.motion.positions[self.frame]
            self.target=pose[0].astype(float).copy()
            self.distance=max(2.8,float(np.ptp(pose,axis=0).max())*2.4)
        self.draw()

    def mouse_down(self,e):self.mouse=(e.x,e.y)

    def orbit(self,e):
        if self.mouse:
            self.yaw+=(e.x-self.mouse[0])*.008
            self.pitch=max(-1.4,min(1.4,self.pitch+(e.y-self.mouse[1])*.006))
        self.mouse=(e.x,e.y);self.draw()

    def pan(self,e):
        if self.mouse:
            dx=(e.x-self.mouse[0])*self.distance*.0015;dy=(e.y-self.mouse[1])*self.distance*.0015
            self.target+=np.array([-math.cos(self.yaw)*dx,dy,math.sin(self.yaw)*dx])
            self.follow_var.set(False)
        self.mouse=(e.x,e.y);self.draw()

    def zoom(self,e):self.distance=max(.3,min(80,self.distance*(.88 if e.delta>0 else 1.14)));self.draw()

    def draw(self):
        if getattr(self.viewport,'context_created',False) and self.viewport.winfo_ismapped():self.viewport._display()

    def render(self):
        w,h=max(1,self.viewport.winfo_width()),max(1,self.viewport.winfo_height())
        GL.glViewport(0,0,w,h);GL.glClearColor(.045,.062,.085,1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT)
        GL.glMatrixMode(GL.GL_PROJECTION);GL.glLoadIdentity();GLU.gluPerspective(45,w/h,.01,250)
        GL.glMatrixMode(GL.GL_MODELVIEW);GL.glLoadIdentity()
        target=self.target.copy()
        if self.motion and self.follow_var.get():target=self.motion.positions[self.frame,0].astype(float)
        cp=math.cos(self.pitch)
        eye=target+self.distance*np.array([math.sin(self.yaw)*cp,math.sin(self.pitch),math.cos(self.yaw)*cp])
        GLU.gluLookAt(*eye,*target,0,1,0)
        GL.glColor3f(.12,.16,.21);GL.glLineWidth(1)
        gx,gz=round(target[0]),round(target[2]);GL.glBegin(GL.GL_LINES)
        for v in range(-25,26):
            GL.glVertex3f(gx+v,0,gz-25);GL.glVertex3f(gx+v,0,gz+25)
            GL.glVertex3f(gx-25,0,gz+v);GL.glVertex3f(gx+25,0,gz+v)
        GL.glEnd()
        if self.motion:
            root=self.motion.positions[:,0]
            for start,end,color in [(0,len(root)-1,(.2,.3,.39)),(self.start,self.end,(.7,.4,.2))]:
                GL.glColor3f(*color);GL.glLineWidth(2);GL.glBegin(GL.GL_LINE_STRIP)
                stride=max(1,(end-start)//1600)
                for p in root[start:end+1:stride]:GL.glVertex3f(float(p[0]),.012,float(p[2]))
                GL.glEnd()
            pos=self.motion.positions[self.frame]
            GL.glLineWidth(5);GL.glColor3f(1.,.66,.35);GL.glBegin(GL.GL_LINES)
            for j,p in enumerate(self.motion.parents):
                if p>=0:GL.glVertex3fv(pos[p]);GL.glVertex3fv(pos[j])
            GL.glEnd();GL.glPointSize(6);GL.glColor3f(.45,.85,.89);GL.glBegin(GL.GL_POINTS)
            for p in pos:GL.glVertex3fv(p)
            GL.glEnd()
        GL.glFlush()

    def close(self):
        if self.busy_save:
            self.status_var.set('Finishing dataset save before closing…');self.after(200,self.close);return
        self.write_draft();self.executor.shutdown(wait=False,cancel_futures=True);self.destroy()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',type=Path,default=DATA)
    args=parser.parse_args()
    mutex=None
    if os.name=='nt':
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
        kernel.CreateMutexW.restype=wintypes.HANDLE
        mutex=kernel.CreateMutexW(None,False,'Local\\'+APP_ID)
        if ctypes.get_last_error()==183:
            user=ctypes.windll.user32
            user.FindWindowW.restype=wintypes.HWND
            hwnd=user.FindWindowW(None,'Lafan Cutter')
            if hwnd:
                user.ShowWindow(hwnd,9);user.SetForegroundWindow(hwnd)
            return
    app=Cutter(args.data_dir)
    app.mainloop()


if __name__=='__main__':
    try:main()
    except Exception:
        DATA.mkdir(parents=True,exist_ok=True)
        (DATA/'startup-error.log').write_text(traceback.format_exc(),encoding='utf-8')
        raise
