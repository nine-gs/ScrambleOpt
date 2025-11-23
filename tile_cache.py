import numpy as np

class TileCache:
    def __init__(self, dem, tile_size=256, max_cache=200):
        self.dem = dem
        self.tile_size = tile_size
        self.max_cache = max_cache
        self.cache = {}
        self.order = []

    def tile_coords(self):
        tx_max = (self.dem.width + self.tile_size - 1) // self.tile_size
        ty_max = (self.dem.height + self.tile_size - 1) // self.tile_size
        for ty in range(ty_max):
            for tx in range(tx_max):
                yield tx, ty

    def get_tile(self, tx, ty):
        key = (tx, ty)
        if key in self.cache:
            self.order.remove(key)
            self.order.append(key)
            return self.cache[key]

        x0 = tx * self.tile_size
        y0 = ty * self.tile_size
        x1 = min(x0 + self.tile_size, self.dem.width)
        y1 = min(y0 + self.tile_size, self.dem.height)

        data = self.dem.get_window(x0, y0, x1, y1)
        if data is None or data.size == 0:
            return None

        tile = data.astype(np.float32)  # keep float precision

        if len(self.cache) >= self.max_cache:
            oldest = self.order.pop(0)
            del self.cache[oldest]

        self.cache[key] = tile
        self.order.append(key)
        return tile
