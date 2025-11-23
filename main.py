import sys, os
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
from dem_loader import DEM
from tile_cache import TileCache
from viewer.dem_viewer import DEMViewer
import config

def main():
    app = QApplication(sys.argv)

    last_folder = config.load_last_folder()
    filepath, _ = QFileDialog.getOpenFileName(
        None, "Open DEM", last_folder, filter="TIFF Files (*.tif *.tiff)"
    )
    if not filepath:
        sys.exit(0)
    config.save_last_folder(os.path.dirname(filepath))

    dem = DEM(filepath)
    tile_cache = TileCache(dem)
    window = QMainWindow()
    viewer = DEMViewer(dem, tile_cache)
    window.setCentralWidget(viewer)
    window.resize(800, 600)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
