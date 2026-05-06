import pytest
from typing import Any
from PyQt6.QtWidgets import QApplication

from gui.settings_panels import (
    CompressionSettingsWidget,
    DestinationSettingsWidget,
    ScheduleSettingsWidget,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Proporciona una instancia de QApplication para las pruebas."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_destination_settings_widget(qapp: QApplication, qtbot: Any) -> None:
    """Prueba la instanciación y lógica del panel de destino."""
    widget = DestinationSettingsWidget()
    qtbot.addWidget(widget)

    assert widget.check_local.isChecked() is True
    assert widget.check_drive.isChecked() is False
    assert widget.btn_auth_drive.isEnabled() is False

    widget.check_drive.setChecked(True)
    assert widget.btn_auth_drive.isEnabled() is True


def test_schedule_settings_widget(qapp: QApplication, qtbot: Any) -> None:
    """Prueba la instanciación del panel de planificación."""
    widget = ScheduleSettingsWidget()
    qtbot.addWidget(widget)

    assert len(widget.day_checks) == 7
    assert "Lunes" in widget.day_checks


def test_compression_settings_widget(qapp: QApplication, qtbot: Any) -> None:
    """Prueba la instanciación del panel de compresión."""
    widget = CompressionSettingsWidget()
    qtbot.addWidget(widget)

    assert widget.radio_zip.isChecked() is True
    assert widget.radio_targz.isChecked() is False
