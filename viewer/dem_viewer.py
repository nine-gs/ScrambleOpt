from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QLabel, QSpinBox, QPushButton, QHBoxLayout, QWidget
from .tile_renderer import TileRenderer
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QFont, QBrush
import numpy as np
from resegmenter import Resegmenter

class DEMViewer(QGraphicsView):
    def __init__(self, dem, tile_cache, path=None):
        super().__init__()
        self.dem = dem
        self.tile_cache = tile_cache
        self.path = path
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.tiles_items = {}
        self.scale_factor = 1.15  # base zoom factor

        # Track cumulative zoom
        self.current_scale = 1.0

        # Zoom bounds
        self.min_scale = 0.01
        self.max_scale = 100
        
        # Path visualization
        self.path_points_items = []
        self.path_is_editing = True  # Start in edit mode
        self.dragging_point_index = None  # Track which point is being dragged
        self.dragging_point_indices = []  # Track clustered points being dragged
        
        # Point selection settings
        self.point_select_radius_screen = 5  # pixels on screen from cursor to select a point
        self.hovered_point_index = None  # Track which point is under cursor
        self.point_graphics_items = {}  # Map point index to graphics item for glow effect
        
        # Middle-click pan tracking
        self.middle_click_drag = False
        self.last_pan_pos = None
        
        # Stats label
        self.stats_label = QLabel(self)
        self.stats_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 180); padding: 5px; font-size: 12px; font-family: monospace;")
        self.stats_label.setGeometry(10, 10, 300, 80)
        
        # Resegment controls (bottom right)
        self.resegment_widget = QWidget(self)
        self.resegment_layout = QHBoxLayout(self.resegment_widget)
        self.resegment_layout.setContentsMargins(5, 5, 5, 5)
        
        self.point_count_spinbox = QSpinBox()
        self.point_count_spinbox.setMinimum(2)
        self.point_count_spinbox.setMaximum(10000)
        self.point_count_spinbox.setValue(10)
        self.point_count_spinbox.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 180);")
        
        self.resegment_button = QPushButton("Resegment")
        self.resegment_button.setStyleSheet("color: white; background-color: rgba(50, 100, 50, 200); padding: 5px;")
        self.resegment_button.clicked.connect(self.on_resegment)
        
        self.simplify_button = QPushButton("Simplify")
        self.simplify_button.setStyleSheet("color: white; background-color: rgba(100, 50, 50, 200); padding: 5px;")
        self.simplify_button.clicked.connect(self.on_simplify)
        
        self.resegment_layout.addWidget(QLabel("Target points:"))
        self.resegment_layout.addWidget(self.point_count_spinbox)
        self.resegment_layout.addWidget(self.resegment_button)
        self.resegment_layout.addWidget(self.simplify_button)
        
        self.resegment_widget.setStyleSheet("background-color: transparent;")
        self.resegment_widget.setGeometry(0, 0, 400, 40)

        self.render_tiles()

        # Disable default drag mode so we can handle panning manually
        self.setDragMode(QGraphicsView.NoDrag)
        # Enable mouse tracking to get mouseMoveEvent even when no buttons are pressed
        self.setMouseTracking(True)
        self.update_stats()

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

    def screen_to_scene_distance(self, screen_pixels):
        """Convert a distance in screen space to scene space"""
        # Get two points in screen space separated by screen_pixels
        p1_screen = self.mapToScene(0, 0)
        p2_screen = self.mapToScene(screen_pixels, 0)
        # Calculate the distance in scene space
        scene_distance = np.sqrt((p2_screen.x() - p1_screen.x())**2 + (p2_screen.y() - p1_screen.y())**2)
        return scene_distance

    def wheelEvent(self, event):
        """Zoom in/out centered on mouse cursor with min/max scale limits"""
        # Get scene position before zoom
        scene_pos = self.mapToScene(event.position().toPoint())
        
        zoom_in = event.angleDelta().y() > 0
        zoom = self.scale_factor if zoom_in else 1 / self.scale_factor

        # Compute tentative new cumulative scale
        new_scale = self.current_scale * zoom
        # Clamp using lightweight np.clip
        clamped_scale = np.clip(new_scale, self.min_scale, self.max_scale)
        # Adjust zoom factor to account for clamping
        effective_zoom = clamped_scale / self.current_scale

        # Zoom around the mouse cursor
        self.scale(effective_zoom, effective_zoom)
        self.current_scale = clamped_scale

        # After zoom, get the new position where the cursor is
        new_scene_pos = self.mapToScene(event.position().toPoint())
        
        # Pan so the same scene point is under the cursor
        delta = scene_pos - new_scene_pos
        self.translate(delta.x(), delta.y())
    
    def mousePressEvent(self, event):
        """Handle mouse clicks for adding points to path"""
        # Middle click: start pan
        if event.button() == Qt.MiddleButton:
            self.middle_click_drag = True
            self.last_pan_pos = event.pos()
            return
        
        if self.path is None:
            return
        
        scene_pos = self.mapToScene(event.pos())
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        
        # Left click: add point in edit mode, or drag existing point
        if event.button() == Qt.LeftButton:
            if not self.path_is_editing:
                # Switch to edit mode
                self.path_is_editing = True
                self.path.locked = False
                self.redraw_path()
                self.update_stats()
                return
            
            # Check if clicking on an existing point (within select radius in screen space)
            points = self.path.get_points()
            scene_radius = self.screen_to_scene_distance(self.point_select_radius_screen)
            clicked_indices = []
            for i, point in enumerate(points):
                px, py = int(point[0]), int(point[1])
                dist = np.sqrt((x - px)**2 + (y - py)**2)
                if dist < scene_radius:
                    clicked_indices.append(i)
            
            if clicked_indices:
                # Start dragging the clicked point(s)
                self.dragging_point_indices = clicked_indices
                self.dragging_point_index = clicked_indices[0]  # Primary point for reference
                return
            
            # Otherwise, add a new point
            try:
                self.path.add_point(x, y)
                self.redraw_path()
                self.update_stats()
            except (ValueError, IndexError) as e:
                print(f"Error adding point: {e}")
        
        # Right click: finalize path (stop editing)
        elif event.button() == Qt.RightButton:
            if self.path_is_editing and len(self.path.get_points()) > 0:
                self.path_is_editing = False
                self.path.locked = True
                self.redraw_path()
                self.update_stats()
        
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle point dragging, clustering, middle-click panning, and hover effects"""
        # Handle middle-click panning
        if self.middle_click_drag and self.last_pan_pos is not None:
            delta = event.pos() - self.last_pan_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self.last_pan_pos = event.pos()
            return
        
        scene_pos = self.mapToScene(event.pos())
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        
        # Handle point dragging (including clustered points)
        if self.dragging_point_index is not None and len(self.dragging_point_indices) > 0:
            # Get the primary point's current position
            primary_point = self.path.points[self.dragging_point_index]
            dx = x - int(primary_point[0])
            dy = y - int(primary_point[1])
            
            # Move all selected points by the same delta
            try:
                for i in self.dragging_point_indices:
                    self.path.shift_point(i, dx, dy, update_z=True)
                self.redraw_path()
                self.update_stats()
            except (ValueError, IndexError) as e:
                print(f"Error shifting point: {e}")
        else:
            # Check for hover over points to show glow
            if self.path_is_editing:
                points = self.path.get_points() if self.path else np.array([]).reshape(0, 3)
                old_hovered = self.hovered_point_index
                self.hovered_point_index = None
                
                scene_radius = self.screen_to_scene_distance(self.point_select_radius_screen)
                for i, point in enumerate(points):
                    px, py = int(point[0]), int(point[1])
                    dist = np.sqrt((x - px)**2 + (y - py)**2)
                    if dist < scene_radius:
                        self.hovered_point_index = i
                        break
                
                # Redraw if hover state changed (to show/remove glow)
                if old_hovered != self.hovered_point_index:
                    self.redraw_path()
            
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle end of point dragging and panning"""
        if event.button() == Qt.LeftButton:
            self.dragging_point_index = None
            self.dragging_point_indices = []
        elif event.button() == Qt.MiddleButton:
            self.middle_click_drag = False
            self.last_pan_pos = None
        super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_Delete and self.path_is_editing:
            # Delete the last point (furthest point)
            if self.path.get_point_count() > 2:  # Keep at least 2 points (start and end)
                try:
                    self.path.delete_point(self.path.get_point_count() - 1)
                    self.redraw_path()
                    self.update_stats()
                except IndexError as e:
                    print(f"Error deleting point: {e}")
        else:
            super().keyPressEvent(event)
    
    def redraw_path(self):
        """Clear and redraw path points and segments on the scene"""
        # Remove old point markers and segments
        for item in self.path_points_items:
            self.scene.removeItem(item)
        self.path_points_items.clear()
        
        points = self.path.get_points()
        
        # Determine line color based on editing state
        if self.path_is_editing:
            line_color = QColor(100, 150, 255)
        else:
            line_color = QColor(50, 50, 80)
        
        # Draw line segments connecting points with zoom-independent line weight
        if len(points) > 1:
            pen = QPen(line_color)
            pen.setCosmetic(True)  # Make line width zoom-independent (always 1 pixel)
            pen.setWidth(2)
            for i in range(len(points) - 1):
                x1, y1 = int(points[i][0]), int(points[i][1])
                x2, y2 = int(points[i + 1][0]), int(points[i + 1][1])
                line = self.scene.addLine(x1, y1, x2, y2, pen)
                line.setZValue(1)
                self.path_points_items.append(line)
        
        # Draw point markers (only visible in edit mode)
        if self.path_is_editing:
            for i, point in enumerate(points):
                x, y = int(point[0]), int(point[1])
                # Different colors for start (green), middle (blue), and end (red) points
                if i == 0:
                    color = QColor(0, 255, 0)
                elif i == len(points) - 1:
                    color = QColor(255, 0, 0)
                else:
                    color = QColor(0, 0, 255)
                
                # Add glow effect if hovered
                if i == self.hovered_point_index:
                    # Draw glow circle first (larger, semi-transparent fill)
                    glow_color = QColor(color.red(), color.green(), color.blue(), 120)
                    glow_pen = QPen(Qt.transparent)
                    glow_brush = QBrush(glow_color)
                    glow = self.scene.addEllipse(x - 10, y - 10, 20, 20, glow_pen, glow_brush)
                    glow.setZValue(1)
                    self.path_points_items.append(glow)
                
                pen = QPen(color)
                pen.setCosmetic(True)
                pen.setWidth(3)
                circle = self.scene.addEllipse(x - 3, y - 3, 6, 6, pen)
                circle.setZValue(2)
                self.path_points_items.append(circle)
    
    def update_stats(self):
        """Update the stats label with path length and elevation gain"""
        if self.path is None or self.path.get_point_count() == 0:
            self.stats_label.setText("No path")
            return
        
        total_distance = self.path.get_total_distance()
        elevation_gain, elevation_loss = self.path.get_elevation_gain_loss()
        point_count = self.path.get_point_count()
        
        stats_text = f"""Path Stats:
Points: {point_count}
Distance: {total_distance:.1f} m
Gain: {elevation_gain:.1f} m
Loss: {elevation_loss:.1f} m
Mode: {'EDIT' if self.path_is_editing else 'FIXED'}"""
        
        self.stats_label.setText(stats_text)
    
    def resizeEvent(self, event):
        """Position resegment controls at bottom right"""
        super().resizeEvent(event)
        # Position at bottom right with 10px margin
        width = self.resegment_widget.sizeHint().width()
        height = self.resegment_widget.sizeHint().height()
        x = self.width() - width - 10
        y = self.height() - height - 10
        self.resegment_widget.setGeometry(x, y, width, height)
    
    def on_resegment(self):
        """Handle resegmentation button click"""
        if self.path is None or self.path.get_point_count() < 2:
            print("No valid path to resegment")
            return
        
        target_count = self.point_count_spinbox.value()
        current_count = self.path.get_point_count()
        
        if target_count <= current_count:
            print(f"Target point count ({target_count}) must be greater than current ({current_count})")
            return
        
        # Resegment the path
        new_path = Resegmenter.resegment(self.path, target_count)
        
        if new_path is None:
            print("Resegmentation failed")
            return
        
        # Replace the path
        self.path = new_path
        self.redraw_path()
        self.update_stats()
        print(f"Path resegmented: {current_count} -> {target_count} points")
    
    def on_simplify(self):
        """Handle path simplification button click"""
        if self.path is None or self.path.get_point_count() < 3:
            print("Path must have at least 3 points to simplify")
            return
        
        original_count = self.path.get_point_count()
        
        # Simplify the path
        new_path = Resegmenter.simplify(self.path)
        
        if new_path is None:
            print("Simplification failed")
            return
        
        new_count = new_path.get_point_count()
        
        # Replace the path
        self.path = new_path
        self.redraw_path()
        self.update_stats()
        print(f"Path simplified: {original_count} -> {new_count} points (removed {original_count - new_count} collinear points)")
