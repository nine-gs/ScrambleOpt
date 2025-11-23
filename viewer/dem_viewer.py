from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from .tile_renderer import TileRenderer
from PySide6.QtCore import Qt
import numpy as np

class DEMViewer(QGraphicsView):
    def __init__(self, dem, tile_cache):
        super().__init__()
        self.dem = dem
        self.tile_cache = tile_cache
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.tiles_items = {}
        self.scale_factor = 1.15  # base zoom factor

        # Track cumulative zoom
        self.current_scale = 1.0

        # Zoom bounds
        self.min_scale = 0.01

        self.max_scale = 100

        self.render_tiles()

        # Enable mouse dragging
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def render_tiles(self):
        for tx, ty in self.tile_cache.tile_coords():
            tile = self.tile_cache.get_tile(tx, ty)
            pixmap = TileRenderer.render(tile)
            if pixmap is None:
                continue
            if (tx, ty) in self.tiles_items:
                self.scene.removeItem(self.tiles_items[(tx, ty)])
            item = self.scene.addPixmap(pixmap)
            item.setPos(tx * self.tile_cache.tile_size, ty * self.tile_cache.tile_size)
            self.tiles_items[(tx, ty)] = item

    def wheelEvent(self, event):
        """Zoom in/out centered on cursor with min/max scale limits"""
        old_pos = self.mapToScene(event.position().toPoint())
        zoom_in = event.angleDelta().y() > 0
        zoom = self.scale_factor if zoom_in else 1 / self.scale_factor

        # Compute tentative new cumulative scale
        new_scale = self.current_scale * zoom
        # Clamp using lightweight np.clip
        clamped_scale = np.clip(new_scale, self.min_scale, self.max_scale)
        # Adjust zoom factor to account for clamping
        effective_zoom = clamped_scale / self.current_scale

        self.scale(effective_zoom, effective_zoom)
        self.current_scale = clamped_scale

        # Keep zoom centered on cursor
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
