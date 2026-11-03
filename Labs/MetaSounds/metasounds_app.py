"""Prophecy MetaSounds - a standalone game-audio sandbox whose projects port to Unreal Engine 5.

Run with the Sound Studio environment:  pythonw.exe metasounds_app.py
"""
from __future__ import annotations

import argparse
import ctypes
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow

HERE = Path(__file__).resolve().parent
APP_ID = 'Prophecy.MetaSounds.Desktop.1'
DATA_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ProphecyMetaSounds'
SOUNDS = Path.home() / 'Documents' / 'Sounds'
MIXED = Path.home() / 'Documents' / 'Sounds Mixed'


class MetaSoundsWindow(QMainWindow):
    def __init__(self, state_dir=DATA_DIR, home=None, libraries=None):
        super().__init__()
        from meta_model import DEFAULT_HOME
        from meta_ui import MetaSoundsTab
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.setWindowTitle('Prophecy MetaSounds')
        self.setWindowIcon(QIcon(str(HERE / 'icon.ico')))
        self.tab = MetaSoundsTab(self, home or DEFAULT_HOME,
                                 libraries or [('Sounds', SOUNDS), ('Sounds Mixed', MIXED)])
        self.setCentralWidget(self.tab)
        self.resize(1500, 940)
        self.setMinimumSize(1200, 700)
        self.started = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self.started:
            self.started = True
            self.tab.activate()

    def closeEvent(self, event):
        self.tab.deactivate()
        self.tab.shutdown()
        event.accept()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', type=Path, default=DATA_DIR)
    args = parser.parse_args()
    args.state_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=args.state_dir / 'metasounds.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    if os.name == 'nt':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv)
    app.setApplicationName('Prophecy MetaSounds')
    app.setOrganizationName('Prophecy')
    app.setStyle('Fusion')
    from meta_theme import STYLE
    app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(str(HERE / 'icon.ico')))
    lock = QLockFile(str(args.state_dir / 'metasounds.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        return 0          # already open
    window = MetaSoundsWindow(args.state_dir)
    screen = app.primaryScreen().availableGeometry()
    window.resize(min(1500, screen.width() - 50), min(960, screen.height() - 60))
    window.show()
    result = app.exec()
    lock.unlock()
    return result


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        logging.exception('MetaSounds startup failed')
        raise
