"""Silver hardware, graphite audio canvas, and colour reserved for signal data."""
from pathlib import Path

BG, PANEL, FIELD = '#202225', '#2c2f34', '#222529'
TEXT, MUTED, LINE = '#e5e7eb', '#b0b4bd', '#4b5058'
CANVAS, CANVAS_TEXT, CANVAS_MUTED = '#3a3d42', '#f0f1f3', '#c1c5cc'
SILVER = 'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #d9dce1,stop:0.5 #bfc4cd,stop:1 #aeb5c0)'
BUTTON = 'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #494e57,stop:1 #363b43)'
CHECK = (Path(__file__).resolve().parent/'check.svg').as_posix()

STYLE = f'''
QWidget {{ color:{TEXT}; font-family:'Segoe UI'; font-size:12px; }}
QMainWindow, QScrollArea, QWidget#canvas {{ background:{BG}; }}
QDialog {{ background:{PANEL}; }}
QFrame#panel {{ background:{PANEL}; border:1px solid {LINE}; border-radius:10px; }}
QFrame#strip {{ background:{PANEL}; border:1px solid {LINE}; border-radius:7px; }}
QFrame#surface {{ background:{CANVAS}; border:1px solid #44484f; border-radius:9px; }}
QFrame#eqStrip {{ background:#32353a; border:0; border-radius:6px; }}
QLabel#muted {{ color:{MUTED}; font-size:11px; }}
QLabel#section {{ color:#bdc3cd; font-size:11px; font-weight:700; letter-spacing:1px; }}
QLabel#title {{ font-size:18px; font-weight:650; }}
QLabel#clipTitle {{ font-size:15px; font-weight:600; }}
QPushButton {{ color:{TEXT}; background:{BUTTON}; border:1px solid #626975; border-radius:5px; padding:5px 9px; font-weight:600; }}
QPushButton:hover {{ background:#565d68; border-color:#929ba9; }}
QPushButton:pressed {{ background:#30353c; border-color:#a2abb8; }}
QPushButton:checked {{ background:{SILVER}; border-color:#e3e6ec; color:#24282e; }}
QPushButton:disabled {{ color:#818792; border-color:#434952; background:#32373e; }}
QPushButton#primary {{ padding:7px 15px; font-size:12px; background:{SILVER}; color:#24282e; border-color:#d9dee6; }}
QPushButton#primary:hover {{ background:#e6e9ee; }}
QPushButton#primary:disabled {{ background:#545c69; color:#959daa; border-color:#68707d; }}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {{ background:{FIELD}; color:{TEXT}; border:1px solid {LINE}; border-radius:5px; padding:5px; selection-background-color:#535c6b; selection-color:white; }}
QDoubleSpinBox, QSpinBox {{ padding:3px; font-size:11px; }}
QDoubleSpinBox QLineEdit, QSpinBox QLineEdit {{ border:0; padding:0; background:transparent; }}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{ border-color:#6f7886; }}
QLineEdit:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {{ color:#848a95; background:#30343a; }}
QComboBox QAbstractItemView {{ background:{FIELD}; color:{TEXT}; selection-background-color:#59616e; selection-color:white; }}
QListWidget {{ background:#25282d; color:{TEXT}; border:1px solid #434952; border-radius:6px; padding:4px; outline:0; }}
QListWidget::item {{ padding:9px 4px; border-radius:4px; font-size:11px; }}
QListWidget::item:hover {{ background:#3b424c; }}
QListWidget::item:selected {{ background:#656e7b; color:white; }}
QSlider::groove:horizontal {{ height:3px; background:#515864; border-radius:1px; }}
QSlider::sub-page:horizontal {{ background:#a3aebb; border-radius:1px; }}
QSlider::handle:horizontal {{ background:#c4cbd6; border:1px solid #e7eaf0; width:10px; margin:-4px 0; border-radius:5px; }}
QSlider::groove:vertical {{ width:5px; background:#42474f; border-radius:2px; }}
QSlider::handle:vertical {{ background:{SILVER}; border:1px solid #f2f4f7; height:15px; margin:0 -6px; border-radius:6px; }}
QCheckBox {{ spacing:7px; }}
QCheckBox::indicator {{ width:15px; height:15px; border-radius:3px; border:1px solid #969ea9; background:{FIELD}; }}
QCheckBox::indicator:checked {{ background:#59616e; border-color:#59616e; image:url({CHECK}); }}
QScrollArea {{ border:0; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar:horizontal {{ background:transparent; height:7px; margin:0; }}
QScrollBar::handle:vertical {{ background:#646d7a; min-height:35px; border-radius:5px; }}
QScrollBar::handle:horizontal {{ background:#646d7a; min-width:35px; border-radius:3px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
QSplitter::handle {{ background:{BG}; width:9px; }}
QProgressBar {{ background:#454c57; border:0; border-radius:3px; max-height:5px; }}
QProgressBar::chunk {{ background:#5b6573; }}
QTabWidget::pane {{ border:0; background:{BG}; }}
QTabBar::tab {{ color:{MUTED}; background:{BG}; border:0; padding:10px 14px; margin-bottom:7px; }}
QTabBar::tab:selected {{ color:{TEXT}; border-bottom:2px solid #606a78; }}

/* Gunmetal control surface: the same silver hardware, with readable inset fields. */
QFrame#surface QLabel, QFrame#surface QCheckBox {{ color:{CANVAS_TEXT}; }}
QFrame#surface QLabel#muted, QFrame#surface QLabel#section {{ color:{CANVAS_MUTED}; }}
QFrame#surface QPushButton {{ color:#dce0e6; background:#30343b; border-color:#50565f; }}
QFrame#surface QPushButton:hover {{ background:#414750; border-color:#9199a6; }}
QFrame#surface QPushButton:pressed {{ background:#545d6b; }}
QFrame#surface QPushButton:checked {{ background:{SILVER}; border-color:#e4e7ec; color:#252a31; }}
QFrame#surface QLineEdit, QFrame#surface QDoubleSpinBox, QFrame#surface QSpinBox {{ color:#e9edf2; background:#181b1f; border-color:#41464e; }}
QFrame#surface QDoubleSpinBox QLineEdit, QFrame#surface QSpinBox QLineEdit {{ border:0; background:transparent; padding:0; }}
QFrame#surface QDoubleSpinBox:focus, QFrame#surface QSpinBox:focus {{ border-color:#9fa8b5; }}
QFrame#surface QSlider::groove:horizontal {{ background:#484e58; }}
QFrame#surface QSlider::sub-page:horizontal {{ background:#aeb7c5; }}
QFrame#surface QSlider::handle:horizontal {{ background:#d3d9e2; border:0; }}
QFrame#surface QCheckBox::indicator {{ background:#292d33; border-color:#626a75; }}
QFrame#surface QCheckBox::indicator:checked {{ background:#747e8c; border-color:#a6afbd; }}
QFrame#surface QPushButton#preview {{ background:{SILVER}; color:#252a31; border-color:#d5dbe4; }}
QFrame#surface QPushButton#preview:hover {{ background:#ffffff; }}
QFrame#surface QPushButton#original {{ background:#514165; border-color:#8b75a5; color:#f0e8fa; }}
QFrame#surface QPushButton#original:checked {{ background:#9172b3; border-color:#c5acd9; color:white; }}
QFrame#surface QPushButton#clean {{ background:#363c45; border-color:#87919e; color:#f0f3f7; }}
QFrame#surface QPushButton#clean:checked {{ background:{SILVER}; border-color:white; color:#242930; }}
QPushButton#resetAll {{ background:#963e51; border-color:#a65162; color:#fff5f7; }}
QPushButton#resetAll:hover {{ background:#b44a60; }}
QPushButton#knobReset, QFrame#surface QPushButton#knobReset {{ padding:0; min-width:18px; max-width:18px; min-height:18px; max-height:18px; border:0; background:transparent; color:#b0b8c4; font-size:14px; }}
QFrame#surface QPushButton#knobReset {{ color:#aab3c0; }}
QPushButton#knobReset:hover {{ background:#515b69; color:white; }}
QFrame#surface QPushButton#knobReset:hover {{ background:#454d59; color:white; }}
'''
