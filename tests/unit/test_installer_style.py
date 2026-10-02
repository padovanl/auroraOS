"""The slideshow's hidden tab container must not paint a light frame."""

from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtGui = pytest.importorskip("PySide6.QtGui")
QtQuickWidgets = pytest.importorskip("PySide6.QtQuickWidgets")


def test_slideshow_container_has_no_light_frame_or_page_padding(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("QT_QUICK_BACKEND", "software")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    palette = QtGui.QPalette(app.palette())
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor("white"))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor("white"))
    window = QtWidgets.QWidget()
    window.setPalette(palette)
    window.setObjectName("mainApp")
    layout = QtWidgets.QVBoxLayout(window)
    pages = QtWidgets.QStackedWidget()
    layout.addWidget(pages)
    execution = QtWidgets.QWidget()
    execution.setObjectName("slideshow")
    pages.addWidget(execution)
    execution_layout = QtWidgets.QVBoxLayout(execution)
    execution_layout.setContentsMargins(0, 0, 0, 0)
    tabs = QtWidgets.QTabWidget()
    execution_layout.addWidget(tabs)
    slide = QtQuickWidgets.QQuickWidget()
    slide.setObjectName("qml")
    slide.setClearColor(QtGui.QColor("#1b1428"))
    tabs.addTab(slide, "Slideshow")
    tabs.addTab(QtWidgets.QWidget(), "Log")
    tabs.tabBar().hide()
    stylesheet = Path(__file__).resolve().parents[2] / "branding/calamares/stylesheet.qss"
    window.setStyleSheet(stylesheet.read_text())
    window.resize(1060, 660)
    window.show()
    try:
        app.processEvents()
        inner_stack = tabs.findChild(QtWidgets.QStackedWidget)
        assert inner_stack.contentsRect() == inner_stack.rect()
        assert pages.contentsRect().left() == 26
        shot = tabs.grab().toImage()
        for x, y in ((0, 0), (shot.width() - 1, 0),
                     (0, shot.height() - 1), (shot.width() - 1, shot.height() - 1)):
            pixel = shot.pixelColor(x, y)
            assert max(pixel.red(), pixel.green(), pixel.blue()) < 100
        tabs.setCurrentIndex(1)
        app.processEvents()
        assert tabs.currentIndex() == 1
        tabs.setCurrentIndex(0)
        app.processEvents()
        assert slide.isVisible()
    finally:
        window.close()