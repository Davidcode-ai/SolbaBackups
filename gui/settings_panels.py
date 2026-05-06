"""
Paneles de configuración de la interfaz gráfica usando PyQt6.
"""

from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


class DestinationSettingsWidget(QWidget):
    """Widget para configurar el destino de las copias de seguridad."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        """Inicializa la interfaz gráfica del widget."""
        layout = QVBoxLayout(self)

        group_box = QGroupBox("Store backups in selected destinations")
        group_layout = QVBoxLayout(group_box)

        self.check_local = QCheckBox("Almacenamiento Local")
        self.check_local.setChecked(True)
        group_layout.addWidget(self.check_local)

        self.check_drive = QCheckBox("Google Drive")
        group_layout.addWidget(self.check_drive)

        self.btn_auth_drive = QPushButton("Autorizar Google Drive")
        self.btn_auth_drive.setEnabled(False)
        self.check_drive.toggled.connect(self.btn_auth_drive.setEnabled)
        group_layout.addWidget(self.btn_auth_drive)

        layout.addWidget(group_box)


class ScheduleSettingsWidget(QWidget):
    """Widget para configurar la programación de las copias de seguridad."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        """Inicializa la interfaz gráfica del widget."""
        layout = QVBoxLayout(self)

        group_box = QGroupBox("Schedule backups")
        group_box.setCheckable(True)
        group_box.setChecked(False)
        group_layout = QVBoxLayout(group_box)

        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Hora de ejecución:"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime(2, 0))  # Por defecto 02:00 AM
        time_layout.addWidget(self.time_edit)
        group_layout.addLayout(time_layout)

        days_layout = QHBoxLayout()
        self.day_checks = {}
        days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        for day in days:
            chk = QCheckBox(day[:3])
            self.day_checks[day] = chk
            days_layout.addWidget(chk)

        group_layout.addLayout(days_layout)
        layout.addWidget(group_box)


class CompressionSettingsWidget(QWidget):
    """Widget para configurar la compresión de las copias de seguridad."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        """Inicializa la interfaz gráfica del widget."""
        layout = QVBoxLayout(self)

        group_box = QGroupBox("Compress backups")
        group_box.setCheckable(True)
        group_box.setChecked(True)
        group_layout = QVBoxLayout(group_box)

        self.radio_zip = QRadioButton("Formato .zip")
        self.radio_zip.setChecked(True)
        self.radio_targz = QRadioButton("Formato .tar.gz")

        self.format_group = QButtonGroup(self)
        self.format_group.addButton(self.radio_zip)
        self.format_group.addButton(self.radio_targz)

        group_layout.addWidget(self.radio_zip)
        group_layout.addWidget(self.radio_targz)

        layout.addWidget(group_box)
