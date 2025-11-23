import rasterio
from rasterio.windows import Window
import numpy as np

class DEM:
    def __init__(self, filepath):
        self.filepath = filepath
        self.dataset = rasterio.open(filepath)
        self.height = self.dataset.height
        self.width = self.dataset.width

    def get_window(self, x0, y0, x1, y1):
        x0 = max(0, min(x0, self.width))
        x1 = max(0, min(x1, self.width))
        y0 = max(0, min(y0, self.height))
        y1 = max(0, min(y1, self.height))
        if x0 >= x1 or y0 >= y1:
            return None
        data = self.dataset.read(1, window=Window(x0, y0, x1-x0, y1-y0))
        return None if data.size == 0 else data

    def get_elevation(self, x, y):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return None
        return self.dataset.read(1, window=Window(x, y, 1, 1))[0,0]
