"""Installer slideshow framing and real progress-bar animation."""

import os
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtGui = pytest.importorskip("PySide6.QtGui")
QtQuickWidgets = pytest.importorskip("PySide6.QtQuickWidgets")
QtCore = pytest.importorskip("PySide6.QtCore")
QtTest = pytest.importorskip("PySide6.QtTest")


@pytest.fixture(scope="module")
def qt_app():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("QT_QPA_PLATFORM", "offscreen")
        patch.setenv("QT_QUICK_BACKEND", "software")
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        yield app


def test_slideshow_container_has_no_light_frame_or_page_padding(qt_app):
    app = qt_app
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


@pytest.mark.parametrize("width", (1060, 640))
def test_installer_progress_animation_keeps_real_value(qt_app, width):
    plugins = Path(os.environ.get("AURORA_INSTALLER_STYLE_PLUGINS", "/usr/lib/aurora/qt6"))
    if not (plugins / "styles/libaurora-installer-style.so").exists():
        pytest.skip("Installer style plugin not built")
    qt_app.addLibraryPath(str(plugins))
    style = QtWidgets.QStyleFactory.create("aurora-installer")
    assert style is not None
    original_style = qt_app.style().objectName()
    qt_app.setStyle(style)
    window = QtWidgets.QWidget()
    window.setObjectName("mainApp")
    layout = QtWidgets.QVBoxLayout(window)
    bar = QtWidgets.QProgressBar()
    bar.setObjectName("exec-progress")
    bar.setRange(0, 10000)
    bar.setValue(3900)
    layout.addWidget(bar)
    other = QtWidgets.QProgressBar()
    other.setValue(39)
    layout.addWidget(other)
    stylesheet = Path(__file__).resolve().parents[2] / "branding/calamares/stylesheet.qss"
    window.setStyleSheet(stylesheet.read_text())
    window.resize(width, 120)
    window.show()
    try:
        QtTest.QTest.qWait(300)
        first = bar.grab().toImage()
        first_style = bar.styleSheet()
        QtTest.QTest.qWait(300)
        second = bar.grab().toImage()
        assert first != second
        assert first_style != bar.styleSheet()
        assert (bar.minimum(), bar.maximum(), bar.value(), bar.text()) == (0, 10000, 3900, "39%")
        assert first.pixelColor(bar.width() * 3 // 4, 4) == second.pixelColor(bar.width() * 3 // 4, 4)
        assert len(bar.findChildren(QtCore.QTimer, "aurora-progress-animation")) == 1
        assert not other.findChildren(QtCore.QTimer, "aurora-progress-animation")
        assert not other.styleSheet()
        bar.setValue(10000)
        final_style = bar.styleSheet()
        QtTest.QTest.qWait(100)
        assert final_style == bar.styleSheet()
        assert bar.text() == "100%"
    finally:
        window.close()
        qt_app.setStyle(original_style)
        qt_app.removeLibraryPath(str(plugins))