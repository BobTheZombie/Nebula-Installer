"""Basic Qt wizard smoke test; no authorization or storage operations."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from nebula_installer.graphical_ui import NebulaWindow


def test_graphical_wizard_constructs_without_running_installer():
    app = QApplication.instance() or QApplication([])
    window = NebulaWindow()
    try:
        assert window.stack.count() == 6
        assert window.windowTitle() == "LPM Linux • Nebula Installer"
        assert window.page_index == 0
        window._set_page(2)
        assert window.mode.currentData() == "repository"
        window.mode.setCurrentIndex(1)
        assert window.mode.currentData() == "source"
    finally:
        window.close()
