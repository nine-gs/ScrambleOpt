# Standard libs
import math
import numpy as np
import copy
import random
# Import SinglePointMover
from perturbers.singlePointMover import SinglePointMover
# Import resegment helper
from resegmenter import resegment

name = "Custom Solver"

def optimize(path, cost_function, perturbers, callback=None, stop_event=None):
    """
    Custom optimization logic that allows increases in cost up to 1 and any decrease.
    Args:
        path: xyzPath object (will not be modified)
        cost_function: function(path) -> float
        perturbers: list of perturber modules, each with a perturb(path) -> xyzPath method
        callback: optional function(path, cost, iter_count) called every N iterations to visualize progress
    Returns:
        best_path: xyzPath object (copy)
        best_cost: float
    """
    current_path = path.shallow_copy()
    current_cost = cost_function(current_path)
    best_path = current_path.shallow_copy()
    best_cost = current_cost

    iter_count = 0

    # Instantiate perturbers if modules exposing a SinglePointMover class are passed
    perturber_objs = []
    for p in perturbers:
        if hasattr(p, "SinglePointMover"):
            perturber_objs.append(p.SinglePointMover(spacing=10.0))
        else:
            perturber_objs.append(p)

    # Remember target number of points to preserve node count via resegmenting
    target_point_count = path.get_point_count()

    # bind locals for speed
    cost_fn = cost_function
    stop_ev = stop_event
    perturbers_local = perturber_objs

    while True:
        # Allow external stop request
        if stop_event is not None:
            try:
                if stop_event.is_set():
                    break
            except Exception:
                # In case a non-threading.Event-like object is passed
                pass
        # Pick a random perturber
        perturber = random.choice(perturbers_local)
        # Allow perturbers that accept optional cost_function and stop_event; try to pass stop_event
        # create a single shallow copy for this perturb call
        path_copy = current_path.shallow_copy()
        try:
            new_path = perturber.perturb(path_copy, cost_fn, stop_ev)
        except TypeError:
            try:
                # maybe perturber expects (path, cost_function)
                new_path = perturber.perturb(path_copy, cost_fn)
            except TypeError:
                # final fallback: only path
                new_path = perturber.perturb(path_copy)
        # Ensure nodes aren't too far apart: require max segment length <= 5% of path length
        try:
            total_len = new_path.get_total_distance()
            if total_len > 0:
                desired_seg_len = total_len * 0.05
                # minimal required number of segments
                desired_segments = int(math.ceil(total_len / max(desired_seg_len, 1e-12)))
                desired_points = max(target_point_count, desired_segments + 1)
                if desired_points > new_path.get_point_count():
                    reseg = resegment(new_path, desired_points)
                    if reseg is not None:
                        new_path = reseg
        except Exception:
            # If anything goes wrong with resegment logic, continue with original candidate
            pass

        # Check stop_event before running possibly expensive cost function
        if stop_ev is not None:
            try:
                if stop_ev.is_set():
                    break
            except Exception:
                pass

        new_cost = cost_fn(new_path)
        delta = new_cost - current_cost

        # Accept if better, or if the increase is less than or equal to 1
        if delta <= 1:
            old_current = current_path
            current_path = new_path
            current_cost = new_cost
            # Notify perturber about accepted move so it can propagate
            try:
                if hasattr(perturber, 'on_move_accepted'):
                    perturber.on_move_accepted(old_current, new_path)
            except Exception:
                pass
            if new_cost < best_cost:
                best_path = new_path.shallow_copy()
                best_cost = new_cost
        else:
            # If perturbation was rejected and perturber had a propagation plan, cancel it
            try:
                if hasattr(perturber, '_propagation') and perturber._propagation is not None:
                    perturber._propagation = None
            except Exception:
                pass
        # Debug logging for accepted/rejected moves
        try:
            if delta <= 1:
                print(f"Solver: iter={iter_count} accepted delta={delta:.4f} cost={current_cost:.4f}")
            else:
                print(f"Solver: iter={iter_count} rejected delta={delta:.4f} new_cost={new_cost:.4f}")
        except Exception:
            pass

        iter_count += 1
        # Call callback every 10 iterations for GUI updates
        if callback and iter_count % 10 == 0:
            callback(best_path, best_cost, iter_count)

        # Termination condition (example: fixed number of iterations)
        if iter_count >= 1000:
            break

    return best_path, best_cost

# Example perturber interface:
# class ExamplePerturber:
#     def perturb(self, path):
#         # Modify and return a new xyzPath
#         return path

# Example usage:
# from cost_functions import acsm_equation
# import perturbers.gaussianRaindrops as gr
# import perturbers.translateAll as ta
# import perturbers.singlePointMover as spm
# best_path, best_cost = optimize(path, acsm_equation, [gr, ta, spm], single_point_spacing=10.0)
