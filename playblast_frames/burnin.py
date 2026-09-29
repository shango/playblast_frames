"""Burn a text label into a captured PNG.

Uses Qt, which Maya already ships, so there is no external encoder to install
alongside the tool.
"""

from PySide6 import QtCore, QtGui


# Font size and margin are both derived from the image height so the label
# looks the same on a 4K capture as it would on a smaller one.
HEIGHT_DIVISOR = 40
MIN_FONT_SIZE = 12


def burn(path, text):
    """Draw text into the bottom-left corner of the PNG at path, in place."""
    image = QtGui.QImage(path)
    if image.isNull():
        raise RuntimeError("Could not read captured image: %s" % path)

    size = max(MIN_FONT_SIZE, image.height() // HEIGHT_DIVISOR)
    font = QtGui.QFont("Consolas")
    font.setStyleHint(QtGui.QFont.Monospace)
    font.setPixelSize(size)
    font.setBold(True)

    rect = QtCore.QRect(size, 0, image.width() - 2 * size, image.height() - size)
    alignment = QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom
    offset = max(1, size // 12)

    painter = QtGui.QPainter(image)
    try:
        painter.setFont(font)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        # Shadow first, so the label stays readable over a bright frame as
        # well as a dark one without laying a bar across the image.
        painter.setPen(QtGui.QColor(0, 0, 0, 200))
        painter.drawText(rect.translated(offset, offset), alignment, text)
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.drawText(rect, alignment, text)
    finally:
        painter.end()

    if not image.save(path):
        raise RuntimeError("Could not write burnt-in image: %s" % path)
