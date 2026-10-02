"""Installer slideshow framing and real progress-bar animation."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap

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


@pytest.fixture
def installer_plugins():
    plugins = Path(os.environ.get("AURORA_INSTALLER_STYLE_PLUGINS", "/usr/lib/aurora/qt6"))
    if not (plugins / "styles/libaurora-installer-style.so").exists():
        pytest.skip("Installer style plugin not built")
    return plugins


@pytest.fixture
def installer_style(qt_app, installer_plugins):
    qt_app.addLibraryPath(str(installer_plugins))
    style = QtWidgets.QStyleFactory.create("aurora-installer")
    assert style is not None
    original_style = qt_app.style().objectName()
    qt_app.setStyle(style)
    try:
        yield style
    finally:
        qt_app.setStyle(original_style)
        qt_app.removeLibraryPath(str(installer_plugins))


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
def test_installer_progress_animation_keeps_real_value(qt_app, installer_style, width):
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


@pytest.mark.parametrize("size", ((1060, 660), (800, 600)))
def test_slideshow_rounding_does_not_change_window_geometry(qt_app, installer_style, size):
    window = QtWidgets.QWidget()
    window.setObjectName("mainApp")
    layout = QtWidgets.QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    execution = QtWidgets.QWidget()
    execution.setObjectName("slideshow")
    layout.addWidget(execution, 1)
    contents = QtWidgets.QVBoxLayout(execution)
    slide = QtQuickWidgets.QQuickWidget()
    slide.setObjectName("qml")
    contents.addWidget(slide)
    navigation = QtWidgets.QWidget()
    buttons = QtWidgets.QHBoxLayout(navigation)
    buttons.setContentsMargins(0, 0, 0, 0)
    for label in ("Back", "Next", "Cancel"):
        button = QtWidgets.QPushButton(label)
        button.setObjectName("view-button-" + label.lower())
        buttons.addWidget(button)
    layout.addWidget(navigation)
    stylesheet = Path(__file__).resolve().parents[2] / "branding/calamares/stylesheet.qss"
    window.setStyleSheet(stylesheet.read_text())
    window.resize(*size)
    window.show()
    try:
        for width, height in (size, (size[0] - 80, size[1] - 40)):
            window.resize(width, height)
            qt_app.processEvents()
            assert window.size() == QtCore.QSize(width, height)
            assert window.mask().isEmpty()
            assert window.contentsMargins() == QtCore.QMargins()
            assert not slide.mask().isEmpty()
            assert not slide.mask().contains(slide.rect().topLeft())
            assert not slide.mask().contains(slide.rect().bottomRight())
            assert slide.mask().contains(slide.rect().center())
            assert slide.mask().boundingRect() == slide.rect()
            assert navigation.layout().contentsMargins().bottom() == 16
            for button in navigation.findChildren(QtWidgets.QPushButton):
                assert navigation.height() - button.geometry().bottom() - 1 >= 16
    finally:
        window.close()


def test_keyboard_qml_loads_with_installer_startup_style(installer_plugins):
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
               QT_PLUGIN_PATH=str(installer_plugins), QT_STYLE_OVERRIDE="aurora-installer")
    env.pop("QT_QUICK_CONTROLS_STYLE", None)
    code = textwrap.dedent("""
        import sys
        from PySide6.QtCore import QAbstractListModel, Property, Qt, QUrl, Signal
        from PySide6.QtQml import QQmlExpression, QQmlPropertyMap
        from PySide6.QtQuickControls2 import QQuickStyle
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtWidgets import QApplication

        class Model(QAbstractListModel):
            changed = Signal()
            def __init__(self, rows):
                super().__init__()
                self.rows = rows
                self.selected = 0
            def rowCount(self, parent):
                return len(self.rows)
            def roleNames(self):
                return {int(Qt.UserRole): b"key", int(Qt.UserRole) + 1: b"label"}
            def data(self, index, role):
                if index.isValid() and int(Qt.UserRole) <= role <= int(Qt.UserRole) + 1:
                    return self.rows[index.row()][role - int(Qt.UserRole)]
            def get_index(self):
                return self.selected
            def set_index(self, value):
                self.selected = value
                self.changed.emit()
            currentIndex = Property(int, get_index, set_index, notify=changed)

        app = QApplication([])
        assert app.style().objectName() == "aurora-installer"
        assert QQuickStyle.name() == "Fusion"
        layouts = Model([("us", "English (US)"), ("it", "Italian")])
        variants = Model([("", "Default")])
        config = QQmlPropertyMap()
        config.insert("keyboardLayoutsModel", layouts)
        config.insert("keyboardVariantsModel", variants)
        page = QQuickWidget()
        warnings = []
        page.engine().warnings.connect(lambda errors: warnings.extend(errors))
        page.rootContext().setContextProperty("config", config)
        page.setSource(QUrl.fromLocalFile(sys.argv[1]))
        assert page.status() == QQuickWidget.Ready, [error.toString() for error in page.errors()]
        page.show()
        app.processEvents()
        selection = QQmlExpression(page.rootContext(), page.rootObject(), "selectLayout('it')")
        assert selection.evaluate()[0] == "Italian"
        assert layouts.currentIndex == 1
        assert not warnings, [error.toString() for error in warnings]
        page.close()
    """)
    result = subprocess.run([sys.executable, "-c", code, str(repo / "branding/calamares/keyboardq.qml")],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr