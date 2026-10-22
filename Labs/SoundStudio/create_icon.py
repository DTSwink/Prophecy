"""Rasterize the app's code-native SVG at Windows icon sizes."""
from pathlib import Path
import struct
from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter

root = Path(__file__).resolve().parent
app = QApplication.instance() or QApplication([])
renderer = QSvgRenderer(str(root/'icon.svg'))
images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    images.append((size, bytes(buffer.data())))
offset = 6 + 16*len(images)
header = struct.pack('<HHH', 0, 1, len(images))
entries = bytearray()
payload = bytearray()
for size, data in images:
    entries.extend(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
    payload.extend(data)
    offset += len(data)
(root/'icon.ico').write_bytes(header+entries+payload)
print(root/'icon.ico')
