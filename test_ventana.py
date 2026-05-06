import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from gui.settings_panels import (
    DestinationSettingsWidget,
    ScheduleSettingsWidget,
    CompressionSettingsWidget
)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SolbaBackups - Configuración")
        self.resize(400, 500)
        
        # Crear widget central y layout principal
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        
        # Instanciar los paneles de configuración existentes en el proyecto
        self.destination_panel = DestinationSettingsWidget()
        self.schedule_panel = ScheduleSettingsWidget()
        self.compression_panel = CompressionSettingsWidget()
        
        # Agregarlos al layout
        layout.addWidget(self.destination_panel)
        layout.addWidget(self.schedule_panel)
        layout.addWidget(self.compression_panel)
        
        # Rellenar espacio sobrante para que los widgets se agrupen arriba
        layout.addStretch()
        
        self.setCentralWidget(central_widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    ventana = MainWindow()
    ventana.show()
    
    sys.exit(app.exec())
