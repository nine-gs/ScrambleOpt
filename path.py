import math
import numpy as np
from typing import List, Tuple, Optional

class xyzPath:
    """
    Stores and manages a path as a series of points in 3D raster space (x, y, z).
    Points are stored in raster coordinates with z values read from a DEM.
    """
    def __init__(self, dem=None):
        """
        Initialize an empty path.
        Args:
            dem: DEM object for reading height values (optional, can be set later)
        """
        self.dem = dem
        self.points = []  # List of [x, y, z] coordinates
        self.locked = False  # When locked, start/end points cannot be modified

    def shallow_copy(self):
        """Return a shallow copy of the path (copies points and locked state, references DEM)."""
        new_path = xyzPath(self.dem)
        new_path.points = [pt.copy() for pt in self.points]
        new_path.locked = self.locked
        return new_path

    
    def __init__(self, dem=None):
        """
        Initialize an empty path.
        
        Args:
            dem: DEM object for reading height values (optional, can be set later)
        """
        self.dem = dem
        self.points = []  # List of [x, y, z] coordinates
        self.locked = False  # When locked, start/end points cannot be modified
    
    def set_dem(self, dem):
        """Set or update the DEM reference."""
        self.dem = dem
    
    def add_point(self, x: float, y: float, z: Optional[float] = None) -> None:
        """
        Add a point to the path. If z is not provided, it will be read from the DEM.
        
        Args:
            x: X coordinate in raster space
            y: Y coordinate in raster space
            z: Z coordinate (elevation). If None, will be read from DEM if available.
        """
        if z is None:
            if self.dem is None:
                raise ValueError("Cannot read z value: no DEM set")
            z = self.dem.get_elevation(int(x), int(y))
            if z is None:
                raise ValueError(f"Could not read elevation at ({x}, {y})")
        
        self.points.append([float(x), float(y), float(z)])
    
    def delete_point(self, index: int) -> None:
        """
        Delete a point at the given index. Cannot delete the first or last point if locked.
        
        Args:
            index: Index of the point to delete
            
        Raises:
            IndexError: If index is out of range or if trying to delete protected points while locked
        """
        if index < 0 or index >= len(self.points):
            raise IndexError(f"Point index {index} out of range [0, {len(self.points)-1}]")
        if self.locked and (index == 0 or index == len(self.points) - 1):
            raise IndexError(f"Cannot delete start or end point when path is locked (index {index})")
        self.points.pop(index)
    
    def shift_point(self, index: int, dx: float, dy: float, update_z: bool = True) -> None:
        """
        Shift a point's x and y position by the given deltas. Cannot shift start or end points if locked.
        
        Args:
            index: Index of the point to shift
            dx: Change in x coordinate
            dy: Change in y coordinate
            update_z: If True, read new z value from DEM at the new position
            
        Raises:
            IndexError: If index is out of range or if trying to shift protected points while locked
        """
        if index < 0 or index >= len(self.points):
            raise IndexError(f"Point index {index} out of range [0, {len(self.points)-1}]")
        if self.locked and (index == 0 or index == len(self.points) - 1):
            raise IndexError(f"Cannot shift start or end point when path is locked (index {index})")
        
        new_x = self.points[index][0] + dx
        new_y = self.points[index][1] + dy
        
        if update_z:
            if self.dem is None:
                raise ValueError("Cannot update z value: no DEM set")
            z = self.dem.get_elevation(int(new_x), int(new_y))
            if z is None:
                raise ValueError(f"Could not read elevation at ({new_x}, {new_y})")
            self.points[index] = [new_x, new_y, z]
        else:
            self.points[index][0] = new_x
            self.points[index][1] = new_y
    
    def update_z_values(self) -> None:
        """
        Update all z values by reading from the DEM at each point's x, y location.
        
        Raises:
            ValueError: If no DEM is set
        """
        if self.dem is None:
            raise ValueError("Cannot update z values: no DEM set")
        
        for point in self.points:
            z = self.dem.get_elevation(int(point[0]), int(point[1]))
            if z is not None:
                point[2] = z
    
    def get_points(self) -> np.ndarray:
        """
        Return all points as a numpy array of shape (n, 3) with columns [x, y, z].
        
        Returns:
            Nx3 numpy array of points, or empty array if no points
        """
        if not self.points:
            return np.array([]).reshape(0, 3)
        return np.array(self.points, dtype=np.float32)
    
    def get_segments(self) -> np.ndarray:
        """
        Compute and return segment information between consecutive points.
        Each row contains [dx, dy, dz, distance] for each segment.
        
        Returns:
            (n-1)x4 numpy array where n is the number of points,
            or empty array if fewer than 2 points
        """
        if len(self.points) < 2:
            return np.array([]).reshape(0, 4)
        
        points = np.array(self.points, dtype=np.float32)
        deltas = np.diff(points, axis=0)  # [dx, dy, dz]
        
        # Calculate 3D distance for each segment
        distances = np.linalg.norm(deltas, axis=1, keepdims=True)
        
        segments = np.hstack([deltas, distances])
        return segments
    
    def get_point_count(self) -> int:
        """Return the number of points in the path."""
        return len(self.points)
    
    def clear(self) -> None:
        """Clear all points from the path."""
        self.points = []
    
    def get_point(self, index: int) -> List[float]:
        """
        Get a specific point.
        
        Args:
            index: Index of the point
            
        Returns:
            [x, y, z] coordinates as a list
            
        Raises:
            IndexError: If index is out of range
        """
        if index < 0 or index >= len(self.points):
            raise IndexError(f"Point index {index} out of range [0, {len(self.points)-1}]")
        return self.points[index].copy()
    
    def get_total_distance(self) -> float:
        """
        Calculate the total path distance (sum of all segment lengths).
        
        Returns:
            Total 3D distance along the path
        """
        segments = self.get_segments()
        if segments.size == 0:
            return 0.0
        return float(np.sum(segments[:, 3]))
    
    def get_elevation_gain_loss(self) -> Tuple[float, float]:
        """
        Calculate total elevation gain and loss along the path.
        
        Returns:
            Tuple of (elevation_gain, elevation_loss)
        """
        segments = self.get_segments()
        if segments.size == 0:
            return 0.0, 0.0
        
        dz = segments[:, 2]
        gain = float(np.sum(dz[dz > 0]))
        loss = float(np.sum(-dz[dz < 0]))
        
        return gain, loss
    
    def is_protected(self, index: int) -> bool:
        """
        Check if a point is protected (start or end point).
        
        Args:
            index: Index of the point to check
            
        Returns:
            True if the point is the first or last point, False otherwise
        """
        if len(self.points) == 0:
            return False
        return index == 0 or index == len(self.points) - 1

    def consolidate_consecutive_clusters(self, max_distance: float = 10) -> None:
        """
        Merge consecutive runs of points where adjacent points are closer than
        `max_distance` (in the same units as x/y coordinates). Consecutive means
        indices are contiguous; non-consecutive close points are not merged.

        The collapsed point position is the mean of the clustered points' x/y
        coordinates; if a DEM is available, the z is re-read from the DEM at
        the rounded mean x/y, otherwise the mean z is used.

        Protected endpoints (when `self.locked` is True) are not merged away.

        This modifies the path in place.
        """
        n = len(self.points)
        if n < 2:
            return

        def dist2(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])

        new_pts = []
        i = 0
        while i < n:
            # if next point is close, start collecting a run
            if i < n - 1 and dist2(self.points[i], self.points[i + 1]) <= max_distance:
                run_indices = [i]
                j = i
                while j < n - 1 and dist2(self.points[j], self.points[j + 1]) <= max_distance:
                    j += 1
                    run_indices.append(j)

                # If locked and run includes protected endpoints, skip collapsing
                if self.locked and (0 in run_indices or (n - 1) in run_indices):
                    for k in run_indices:
                        new_pts.append(self.points[k].copy())
                    i = j + 1
                    continue

                # Compute mean x,y and determine z
                xs = [self.points[k][0] for k in run_indices]
                ys = [self.points[k][1] for k in run_indices]
                mean_x = float(np.mean(xs))
                mean_y = float(np.mean(ys))
                if self.dem is not None:
                    try:
                        z = self.dem.get_elevation(int(mean_x), int(mean_y))
                        if z is None:
                            zs = [self.points[k][2] for k in run_indices]
                            z = float(np.mean(zs))
                    except Exception:
                        zs = [self.points[k][2] for k in run_indices]
                        z = float(np.mean(zs))
                else:
                    zs = [self.points[k][2] for k in run_indices]
                    z = float(np.mean(zs))

                new_pts.append([mean_x, mean_y, z])
                i = j + 1
            else:
                new_pts.append(self.points[i].copy())
                i += 1

        self.points = new_pts
