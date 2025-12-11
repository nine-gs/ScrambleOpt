import sys, os
import signal
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PySide6.QtCore import QTimer
from dem_loader import DEM
from tile_cache import TileCache
from path import xyzPath
from viewer.dem_viewer import DEMViewer
import config


def main():
    app = QApplication(sys.argv)

    # Ensure Ctrl-C closes the Qt app cleanly from the terminal
    try:
        signal.signal(signal.SIGINT, lambda *args: app.quit())
    except Exception:
        pass

    # Create a main window placeholder; we'll populate it once a file is chosen
    main_window = QMainWindow()

    def on_file_selected(filepath):
        if not filepath:
            app.quit()
            return
        config.save_last_folder(os.path.dirname(filepath))
        dem = DEM(filepath)
        tile_cache = TileCache(dem)
        path = xyzPath(dem)
        viewer = DEMViewer(dem, tile_cache, path)
        main_window.setCentralWidget(viewer)
        main_window.resize(1200, 600)
        main_window.setMinimumWidth(800)
        main_window.setMinimumHeight(500)
        main_window.show()

    def open_file_dialog():
        last_folder = config.load_last_folder() or os.getcwd()
        dialog = QFileDialog(main_window, "Open DEM")
        dialog.setDirectory(last_folder)
        dialog.setNameFilter("TIFF Files (*.tif *.tiff)")
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.fileSelected.connect(on_file_selected)
        dialog.rejected.connect(app.quit)
        dialog.open()

    # Open the file dialog once the event loop starts to avoid blocking the interpreter
    QTimer.singleShot(0, open_file_dialog)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
