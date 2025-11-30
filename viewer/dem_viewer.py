from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QLabel, QSpinBox, QDoubleSpinBox, QPushButton, QHBoxLayout, QWidget, QComboBox, QVBoxLayout, QGraphicsBlurEffect
from .tile_renderer import TileRenderer
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QFont, QBrush, QPixmap, QImage, QPainter
import numpy as np
from resegmenter import Resegmenter
from plugin_loader import PluginLoader
try:
    from PIL import Image, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class BlurredPanel(QWidget):
    """Custom widget that draws a semi-transparent background"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.background_pixmap = None
    
    def set_background(self, pixmap):
        self.background_pixmap = pixmap
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        
        if self.background_pixmap and not self.background_pixmap.isNull():
            # Draw the blurred background
            painter.drawPixmap(0, 0, self.width(), self.height(), self.background_pixmap)
        
        # Draw semi-transparent overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        painter.end()


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
        
        # Load plugins
        self.solvers = PluginLoader.load_solvers()
        self.cost_functions = PluginLoader.load_cost_functions()
        self.selected_cost_function = None
        self.selected_solver = None
        self.current_cost = None
        
        # Top panel with blur effect (backing for all top widgets)
        self.top_panel = BlurredPanel(self)
        self.top_panel_height = 100
        
        # Stats label (top left, inside top panel)
        self.stats_label = QLabel(self)
        self.stats_label.setStyleSheet("color: white; padding: 5px; font-size: 12px; font-family: monospace; background-color: transparent;")
        self.stats_label.setGeometry(10, 10, 300, 80)
        
        # Solver dropdown (top left, right of stats)
        self.solver_widget = QWidget(self)
        self.solver_layout = QHBoxLayout(self.solver_widget)
        self.solver_layout.setContentsMargins(5, 5, 5, 5)
        
        self.solver_label = QLabel("Solver:")
        self.solver_label.setStyleSheet("color: white; background-color: transparent;")
        self.solver_combo = QComboBox()
        self.solver_combo.addItems(sorted(self.solvers.keys()))
        self.solver_combo.currentTextChanged.connect(self.on_solver_selected)
        self.solver_combo.setStyleSheet("color: white; background-color: rgba(30, 30, 30, 200); border: 1px solid white; padding: 4px;")
        self.solver_combo.view().setMinimumWidth(200)
        
        self.solver_layout.addWidget(self.solver_label)
        self.solver_layout.addWidget(self.solver_combo)
        self.solver_widget.setStyleSheet("background-color: transparent;")
        
        # Cost function dropdown and display (top right)
        self.cost_widget = QWidget(self)
        self.cost_layout = QHBoxLayout(self.cost_widget)
        self.cost_layout.setContentsMargins(5, 5, 5, 5)
        
        self.cost_label = QLabel("Cost Function:")
        self.cost_label.setStyleSheet("color: white; background-color: transparent;")
        self.cost_combo = QComboBox()
        self.cost_combo.addItems(sorted(self.cost_functions.keys()))
        self.cost_combo.currentTextChanged.connect(self.on_cost_function_selected)
        self.cost_combo.setStyleSheet("color: white; background-color: rgba(30, 30, 30, 200); border: 1px solid white; padding: 4px;")
        self.cost_combo.view().setMinimumWidth(250)
        # Make dropdown clickable
        self.cost_combo.setFocusPolicy(Qt.StrongFocus)
        
        # Cost display label (to the right of cost combo)
        self.cost_display_label = QLabel(self)
        self.cost_display_label.setStyleSheet("color: white; padding: 5px; font-size: 12px; font-family: monospace; background-color: transparent;")
        self.cost_display_label.setMinimumWidth(120)
        self.update_cost_display()
        
        self.cost_layout.addWidget(self.cost_label)
        self.cost_layout.addWidget(self.cost_combo)
        self.cost_layout.addWidget(self.cost_display_label)
        
        self.cost_widget.setStyleSheet("background-color: transparent;")
        
        # Available time input (top right, below cost function)
        self.time_widget = QWidget(self)
        self.time_layout = QHBoxLayout(self.time_widget)
        self.time_layout.setContentsMargins(5, 5, 5, 5)
        
        self.time_label = QLabel("Available Time (hrs):")
        self.time_label.setStyleSheet("color: white; background-color: transparent;")
        self.time_spinbox = QDoubleSpinBox()
        self.time_spinbox.setMinimum(0.01)
        self.time_spinbox.setMaximum(999.99)
        self.time_spinbox.setValue(1.0)
        self.time_spinbox.setSingleStep(0.5)
        self.time_spinbox.setDecimals(2)
        self.time_spinbox.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 180);")
        
        self.time_layout.addWidget(self.time_label)
        self.time_layout.addWidget(self.time_spinbox)
        
        self.time_widget.setStyleSheet("background-color: transparent;")
        
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
        
        # Solver run button (bottom center)
        self.run_solver_widget = QWidget(self)
        self.run_solver_layout = QHBoxLayout(self.run_solver_widget)
        self.run_solver_layout.setContentsMargins(5, 5, 5, 5)
        
        self.run_solver_button = QPushButton()
        self.run_solver_button.setStyleSheet("color: white; background-color: rgba(50, 50, 150, 200); padding: 8px; font-weight: bold;")
        self.run_solver_button.clicked.connect(self.on_run_solver)
        self.update_run_button()
        
        self.run_solver_layout.addStretch()
        self.run_solver_layout.addWidget(self.run_solver_button)
        self.run_solver_layout.addStretch()
        
        self.run_solver_widget.setStyleSheet("background-color: transparent;")
        
        # Bottom panel with gradient background
        self.bottom_panel = BlurredPanel(self)
        self.bottom_panel_height = 60
        
        # Print message label (bottom left)
        self.print_label = QLabel(self)
        self.print_label.setStyleSheet("color: yellow; padding: 5px; font-size: 11px; font-family: monospace; background-color: transparent;")
        self.print_label.setText("")
        self.print_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.render_tiles()
        
        # Disable default drag mode so we can handle panning manually
        self.setDragMode(QGraphicsView.NoDrag)
        # Enable mouse tracking to get mouseMoveEvent even when no buttons are pressed
        self.setMouseTracking(True)
        self.update_stats()
        
        # Show and raise all widgets to ensure they're visible above scene
        self.top_panel.show()
        self.stats_label.show()
        self.solver_widget.show()
        self.cost_widget.show()
        self.time_widget.show()
        self.cost_display_label.show()
        self.bottom_panel.show()
        self.print_label.show()
        self.resegment_widget.show()
        self.run_solver_widget.show()
        
        # Raise widgets above scene
        self.top_panel.raise_()
        self.stats_label.raise_()
        self.solver_widget.raise_()
        self.cost_widget.raise_()
        self.time_widget.raise_()
        self.cost_display_label.raise_()
        self.bottom_panel.raise_()
        self.print_label.raise_()
        self.resegment_widget.raise_()
        self.run_solver_widget.raise_()
        
        # Trigger initial selection after all widgets are ready
        if self.solver_combo.count() > 0:
            self.on_solver_selected(self.solver_combo.itemText(0))
        if self.cost_combo.count() > 0:
            self.on_cost_function_selected(self.cost_combo.itemText(0))

    def blur_background(self):
        """Create a gradient background for the top panel"""
        try:
            # Create a simple smooth gradient background
            width = int(self.width())
            height = self.top_panel_height
            
            if width <= 0 or height <= 0:
                return
            
            # Create gradient array (dark at top, lighter at bottom)
            arr = np.zeros((height, width, 4), dtype=np.uint8)
            for y in range(height):
                # Gradient from dark (30) to lighter (80)
                shade = int(30 + (y / height) * 50)
                arr[y, :] = [shade, shade, shade, 255]
            
            # Smooth it with a slight blur
            if PIL_AVAILABLE:
                pil_image = Image.fromarray(arr, 'RGBA')
                blurred = pil_image.filter(ImageFilter.GaussianBlur(radius=5))
                blurred_arr = np.array(blurred)
            else:
                blurred_arr = arr
            
            # Convert to QPixmap
            q_img = QImage(bytes(blurred_arr), width, height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(q_img)
            
            # Set on panel
            self.top_panel.set_background(pixmap)
        except Exception as e:
            print(f"Background creation failed: {e}")
    
    def blur_background_bottom(self):
        """Create a gradient background for the bottom panel (reverse gradient)"""
        try:
            # Create a simple smooth gradient background
            width = int(self.width())
            height = self.bottom_panel_height
            
            if width <= 0 or height <= 0:
                return
            
            # Create gradient array (lighter at top, dark at bottom)
            arr = np.zeros((height, width, 4), dtype=np.uint8)
            for y in range(height):
                # Gradient from lighter (80) to dark (30)
                shade = int(80 - (y / height) * 50)
                arr[y, :] = [shade, shade, shade, 255]
            
            # Smooth it with a slight blur
            if PIL_AVAILABLE:
                pil_image = Image.fromarray(arr, 'RGBA')
                blurred = pil_image.filter(ImageFilter.GaussianBlur(radius=5))
                blurred_arr = np.array(blurred)
            else:
                blurred_arr = arr
            
            # Convert to QPixmap
            q_img = QImage(bytes(blurred_arr), width, height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(q_img)
            
            # Set on panel
            self.bottom_panel.set_background(pixmap)
        except Exception as e:
            print(f"Background creation failed: {e}")

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
        
        # Refresh blurred background after tiles render
        self.blur_background()
        
        # Ensure panels stay behind widgets
        self.top_panel.stackUnder(self.stats_label)
        self.bottom_panel.stackUnder(self.print_label)

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
    
    def update_cost_display(self):
        """Update the cost display label"""
        if self.current_cost is not None:
            cost_html = f"Cost: <span style='font-size: 18px;'><b>{self.current_cost:.1f}</b></span>"
            self.cost_display_label.setText(cost_html)
        else:
            self.cost_display_label.setText("")
    
    def add_print_message(self, message):
        """Add a message to the print label and console"""
        print(str(message))
        self.print_label.setText(str(message))
    
    def update_run_button(self):
        """Update the run solver button text"""
        if self.selected_solver:
            self.run_solver_button.setText("Run Solver")
            self.run_solver_button.setEnabled(True)
        else:
            self.run_solver_button.setText("No Solver Selected")
            self.run_solver_button.setEnabled(False)
    
    def on_solver_selected(self, solver_name):
        """Handle solver selection"""
        if solver_name:  # Always true now since blank is gone
            self.selected_solver = solver_name
            self.update_run_button()
    
    def on_cost_function_selected(self, func_name):
        """Handle cost function selection and calculation"""
        if func_name:  # Always true now since blank is gone
            self.selected_cost_function = func_name
            cost_func = self.cost_functions.get(func_name)
            if cost_func and self.path:
                try:
                    self.current_cost = cost_func(self.path)
                except Exception as e:
                    print(f"Error calculating cost: {e}")
                    self.current_cost = None
            self.update_cost_display()
    
    def on_run_solver(self):
        """Handle run solver button click"""
        if not self.selected_solver:
            self.add_print_message("No solver selected")
            return
        if not self.path or self.path.get_point_count() < 2:
            self.add_print_message("No valid path")
            return
        self.add_print_message(f"Running solver: {self.selected_solver}")
    
    def resizeEvent(self, event):
        """Position UI elements at proper locations"""
        super().resizeEvent(event)
        
        # Position and layer top panel
        self.top_panel.setGeometry(0, 0, self.width(), self.top_panel_height)
        self.top_panel.stackUnder(self.stats_label)  # Keep below widgets
        self.blur_background()
        
        # Position stats label (top left) - wider and taller to prevent clipping
        self.stats_label.setGeometry(10, 10, 300, 80)
        
        # Position solver dropdown (centered horizontally, offset 150px left)
        solver_width = self.solver_widget.sizeHint().width()
        solver_height = self.solver_widget.sizeHint().height()
        solver_x = (self.width() - solver_width) // 2 - 150
        solver_y = 10
        self.solver_widget.setGeometry(solver_x, solver_y, solver_width, solver_height)
        
        # Position cost function dropdown at top right
        cost_width = self.cost_widget.sizeHint().width()
        cost_height = self.cost_widget.sizeHint().height()
        cost_x = self.width() - cost_width - 10
        cost_y = 10
        self.cost_widget.setGeometry(cost_x, cost_y, cost_width, cost_height)
        
        # Position time input below cost function (top right)
        time_width = self.time_widget.sizeHint().width()
        time_height = self.time_widget.sizeHint().height()
        time_x = self.width() - time_width - 10
        time_y = cost_y + cost_height + 5
        self.time_widget.setGeometry(time_x, time_y, time_width, time_height)
        
        # Position bottom panel
        self.bottom_panel.setGeometry(0, self.height() - self.bottom_panel_height, self.width(), self.bottom_panel_height)
        self.bottom_panel.stackUnder(self.print_label)  # Keep below widgets
        self.blur_background_bottom()
        
        # Position resegment controls at bottom right
        reseg_width = self.resegment_widget.sizeHint().width()
        reseg_height = self.resegment_widget.sizeHint().height()
        reseg_x = self.width() - reseg_width - 10
        reseg_y = self.height() - reseg_height - 10
        self.resegment_widget.setGeometry(reseg_x, reseg_y, reseg_width, reseg_height)
        
        # Position print message label (bottom left, aligned with cost_display_label horizontally, centered with resegment button vertically)
        print_y = reseg_y + (reseg_height // 2) - 15  # Center vertically with resegment button
        self.print_label.setGeometry(10, print_y, 400, 30)
        
        # Position solver run button at bottom center
        run_width = self.run_solver_widget.sizeHint().width()
        run_height = self.run_solver_widget.sizeHint().height()
        x = (self.width() - run_width) // 2
        y = self.height() - run_height - 10
        self.run_solver_widget.setGeometry(x, y, run_width, run_height)
    
    def on_resegment(self):
        """Handle resegmentation button click"""
        if self.path is None or self.path.get_point_count() < 2:
            self.add_print_message("No valid path to resegment")
            return
        
        target_count = self.point_count_spinbox.value()
        current_count = self.path.get_point_count()
        
        if target_count <= current_count:
            self.add_print_message(f"Target point count ({target_count}) must be greater than current ({current_count})")
            return
        
        # Resegment the path
        new_path = Resegmenter.resegment(self.path, target_count)
        
        if new_path is None:
            self.add_print_message("Resegmentation failed")
            return
        
        # Replace the path
        self.path = new_path
        self.redraw_path()
        self.update_stats()
        self.add_print_message(f"Path resegmented: {current_count} -> {target_count} points")
    
    def on_simplify(self):
        """Handle path simplification button click"""
        if self.path is None or self.path.get_point_count() < 3:
            self.add_print_message("Path must have at least 3 points to simplify")
            return
        
        original_count = self.path.get_point_count()
        
        # Simplify the path
        new_path = Resegmenter.simplify(self.path)
        
        if new_path is None:
            self.add_print_message("Simplification failed")
            return
        
        new_count = new_path.get_point_count()
        
        # Replace the path
        self.path = new_path
        self.redraw_path()
        self.update_stats()
        self.add_print_message(f"Path simplified: {original_count} -> {new_count} points (removed {original_count - new_count} collinear points)")
