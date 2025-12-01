import numpy as np

def resegment(path, target_point_count):
    """
    Add points to a path to reach the target point count.
    Original points remain at their exact positions.
    New points are added between existing points proportionally to segment length.
    
    Args:
        path: xyzPath object to resegment
        target_point_count: Desired total number of points in the path
        
    Returns:
        New xyzPath with resegmented points, or None if target <= current points
    """
    current_count = path.get_point_count()
    
    if target_point_count <= current_count:
        return None
    
    points_to_add = target_point_count - current_count
    segments = path.get_segments()
    
    if len(segments) == 0:
        return None
    
    # Get segment lengths
    segment_lengths = segments[:, 3]
    total_length = np.sum(segment_lengths)
    
    # Calculate how many points to add to each segment proportionally
    points_per_segment = (segment_lengths / total_length) * points_to_add
    
    # Round to integers and distribute remainder
    points_to_add_per_segment = np.round(points_per_segment).astype(int)
    remainder = points_to_add - np.sum(points_to_add_per_segment)
    
    # Distribute remainder to segments with highest fractional parts
    fractional_parts = points_per_segment - np.floor(points_per_segment)
    if remainder > 0:
        top_indices = np.argsort(fractional_parts)[-remainder:]
        for idx in top_indices:
            points_to_add_per_segment[idx] += 1
    
    # Build new path by interpolating points
    new_points = []
    original_points = path.get_points()
    
    for seg_idx in range(len(segments)):
        # Add the starting point of this segment
        new_points.append(original_points[seg_idx].copy())
        
        # Add interpolated points for this segment
        num_new_points = points_to_add_per_segment[seg_idx]
        if num_new_points > 0:
            p1 = original_points[seg_idx]
            p2 = original_points[seg_idx + 1]
            
            for i in range(1, num_new_points + 1):
                # Linear interpolation
                t = i / (num_new_points + 1)
                interp_point = p1 + t * (p2 - p1)
                new_points.append(interp_point)
    
    # Add the final point
    new_points.append(original_points[-1].copy())
    
    # Create new path with the same DEM
    from path import xyzPath
    new_path = xyzPath(path.dem)
    new_path.locked = path.locked
    
    # Add all points to the new path
    for point in new_points:
        new_path.points.append(list(point))
    
    return new_path

def simplify(path, tolerance=1e-3):
    """
    Simplify a path by removing collinear points.
    Three consecutive points are considered collinear if they lie on the same line
    within the specified tolerance.
    
    Args:
        path: xyzPath object to simplify
        tolerance: Tolerance for considering points as collinear (default 1e-6)
        
    Returns:
        New xyzPath with collinear points removed
    """
    original_points = path.get_points()
    
    if len(original_points) <= 2:
        # Can't simplify paths with 2 or fewer points
        from path import xyzPath
        new_path = xyzPath(path.dem)
        new_path.locked = path.locked
        for point in original_points:
            new_path.points.append(list(point))
        return new_path
    
    # Keep track of which points to keep
    points_to_keep = [0]  # Always keep the first point
    
    for i in range(1, len(original_points) - 1):
        p_prev = original_points[i - 1]
        p_curr = original_points[i]
        p_next = original_points[i + 1]
        
        # Calculate vectors
        v1 = p_curr - p_prev  # Vector from prev to curr
        v2 = p_next - p_curr  # Vector from curr to next
        
        # Normalize vectors
        len_v1 = np.linalg.norm(v1)
        len_v2 = np.linalg.norm(v2)
        
        if len_v1 < tolerance or len_v2 < tolerance:
            # Degenerate case - keep the point
            points_to_keep.append(i)
            continue
        
        v1_norm = v1 / len_v1
        v2_norm = v2 / len_v2
        
        # Calculate cross product (in 3D this gives a vector perpendicular to both)
        cross = np.cross(v1_norm, v2_norm)
        cross_magnitude = np.linalg.norm(cross)
        
        # If cross product magnitude is above tolerance, points are NOT collinear
        if cross_magnitude > tolerance:
            points_to_keep.append(i)
    
    points_to_keep.append(len(original_points) - 1)  # Always keep the last point
    
    # Create new path with only the kept points
    from path import xyzPath
    new_path = xyzPath(path.dem)
    new_path.locked = path.locked
    
    for i in points_to_keep:
        new_path.points.append(list(original_points[i]))
    
    return new_path

# For backward compatibility
class Resegmenter:
    @staticmethod
    def resegment(path, target_point_count):
        return resegment(path, target_point_count)
    @staticmethod
    def simplify(path, tolerance=1e-3):
        return simplify(path, tolerance)

