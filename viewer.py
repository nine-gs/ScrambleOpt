from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QImage, QPixmap

class DEMViewer(QGraphicsView):
    def __init__(self, dem, tile_size=256):
        super().__init__()
        from tile_cache import TileCache

        self.dem = dem
        self.tile_cache = TileCache(dem, tile_size)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.zoom = 1.0
        self.tiles_items = {}
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.render_tiles()

    def render_tiles(self):
        """
        Render tiles that intersect the visible viewport
        """
        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        tx_min = int(visible_rect.left() // self.tile_cache.tile_size)
        ty_min = int(visible_rect.top() // self.tile_cache.tile_size)
        tx_max = int(visible_rect.right() // self.tile_cache.tile_size) + 1
        ty_max = int(visible_rect.bottom() // self.tile_cache.tile_size) + 1

        for ty in range(ty_min, ty_max):
            for tx in range(tx_min, tx_max):
                tile = self.tile_cache.get_tile(tx, ty)
                if tile is None:
                    continue  # skip empty/out-of-bounds tiles
                h, w = tile.shape
                img = QImage(tile.data, w, h, w, QImage.Format.Format_Grayscale8)
                pixmap = QPixmap.fromImage(img)

                if (tx, ty) in self.tiles_items:
                    self.scene.removeItem(self.tiles_items[(tx, ty)])

                item = QGraphicsPixmapItem(pixmap)
                item.setPos(tx * self.tile_cache.tile_size, ty * self.tile_cache.tile_size)
                self.scene.addItem(item)
                self.tiles_items[(tx, ty)] = item

    def wheelEvent(self, event):
        """
        Zoom in/out around cursor
        """
        factor = 1.25
        if event.angleDelta().y() > 0:
            self.zoom *= factor
        else:
            self.zoom /= factor

        old_pos = self.mapToScene(event.position().toPoint())
        self.resetTransform()
        self.scale(self.zoom, self.zoom)
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        self.render_tiles()
