"""Small, safe embedded browser window for Brahma AI Evo.

The browser deliberately accepts only ordinary HTTP(S) destinations. It is a
viewer/navigation surface, not a replacement for the Playwright automation
tool. Sites may restrict playback, sign-in, DRM, or embedded media.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def normalize_browser_url(value: str) -> str:
    """Return a validated HTTP(S) URL, adding https:// when omitted."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Enter a website address.")
    if any(ord(char) < 32 for char in raw):
        raise ValueError("The address contains invalid control characters.")
    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// websites are supported.")
    if not parsed.hostname:
        raise ValueError("Enter a valid website address.")
    if parsed.username or parsed.password:
        raise ValueError("Addresses containing embedded credentials are not allowed.")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("The website address contains an invalid port.") from exc

    return urlunsplit((scheme, parsed.netloc, parsed.path or "/", parsed.query, parsed.fragment))


def create_embedded_browser_window(parent=None):
    """Create the QtWebEngine window lazily so non-GUI tests can import this module."""
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import (
            QLineEdit, QMainWindow, QMessageBox, QToolBar, QVBoxLayout, QWidget,
        )
        from PyQt6.QtWebEngineCore import QWebEnginePage
        from PyQt6.QtWebEngineWidgets import QWebEngineView
    except Exception as exc:
        raise RuntimeError(
            "QtWebEngine is unavailable. Install the PyQt6-WebEngine package and restart Brahma."
        ) from exc

    class SafePage(QWebEnginePage):
        def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
            scheme = (url.scheme() or "").lower()
            if scheme in {"http", "https"}:
                return super().acceptNavigationRequest(url, navigation_type, is_main_frame)
            if scheme == "about" and url.toString() == "about:blank":
                return super().acceptNavigationRequest(url, navigation_type, is_main_frame)
            return False

    class EmbeddedBrowserWindow(QMainWindow):
        def __init__(self, owner=None):
            super().__init__(owner)
            self.setWindowTitle("Brahma • Embedded Browser")
            self.resize(1180, 780)
            self.setMinimumSize(720, 480)

            toolbar = QToolBar("Browser")
            toolbar.setMovable(False)
            self.addToolBar(toolbar)

            back_action = QAction("←", self)
            back_action.setToolTip("Back")
            back_action.triggered.connect(lambda: self.view.back())
            toolbar.addAction(back_action)

            forward_action = QAction("→", self)
            forward_action.setToolTip("Forward")
            forward_action.triggered.connect(lambda: self.view.forward())
            toolbar.addAction(forward_action)

            reload_action = QAction("↻", self)
            reload_action.setToolTip("Reload")
            reload_action.triggered.connect(lambda: self.view.reload())
            toolbar.addAction(reload_action)

            self.address = QLineEdit()
            self.address.setPlaceholderText("Enter a website address (https://...)")
            self.address.returnPressed.connect(self._navigate_from_address)
            toolbar.addWidget(self.address)

            go_action = QAction("Go", self)
            go_action.triggered.connect(self._navigate_from_address)
            toolbar.addAction(go_action)

            self.view = QWebEngineView(self)
            self.view.setPage(SafePage(self.view))
            self.view.urlChanged.connect(self._sync_address)
            self.view.loadFinished.connect(self._load_finished)
            self.setCentralWidget(self.view)
            self.statusBar().showMessage("Ready • HTTP(S) websites only")

        def navigate(self, address: str):
            safe_address = normalize_browser_url(address)
            self.address.setText(safe_address)
            self.view.setUrl(QUrl(safe_address))

        def _navigate_from_address(self):
            try:
                self.navigate(self.address.text())
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid website address", str(exc))

        def _sync_address(self, url):
            self.address.setText(url.toString())

        def _load_finished(self, success: bool):
            if success:
                self.statusBar().showMessage("Page loaded. Some sites may limit embedded playback or sign-in.", 7000)
            else:
                self.statusBar().showMessage("This page could not be loaded in the embedded browser.", 8000)

    return EmbeddedBrowserWindow(parent)
