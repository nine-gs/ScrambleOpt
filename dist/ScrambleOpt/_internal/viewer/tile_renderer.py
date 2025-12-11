from PySide6.QtGui import QImage, QPixmap
import numpy as np
from hillshade import hillshade

class TileRenderer:
    @staticmethod
    def render(tile_array):
        if tile_array is None or tile_array.size == 0:
            return None
        tile_float = tile_array.astype(np.float32)
        hs = hillshade(tile_float)               # compute hillshade
        hs_img = (hs * 255).astype(np.uint8)    # scale for display
        h, w = hs_img.shape
        qimg = QImage(hs_img.data, w, h, w, QImage.Format.Format_Grayscale8)
        return QPixmap.fromImage(qimg)
