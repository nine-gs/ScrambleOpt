import math
import random
import numpy as np

name = "Relocate Point Mover"


class SinglePointMover:
    """Relocate a single interior point by local sampling and hill-climb.

    Algorithm:
    1. Pick a random interior vertex.
    2. Sample a set of candidate offsets in a circular neighborhood.
    3. Evaluate candidate paths and pick the best.
    4. Optionally perform a small local hill-climb around the best candidate.

    This perturber does NOT perform any automatic resegmenting or simplification;
    keep manual resegmenting via the UI if desired.
    The perturber returns a modified `xyzPath` (a fresh object) and leaves
    acceptance to the outer optimization routine.
    """

    def __init__(self, spacing=10.0, samples=16, max_climb_steps=6):
        self.spacing = spacing
        self.samples = samples
        self.max_climb_steps = max_climb_steps
        # propagation state: dict or None
        # {'center': idx, 'dx': dx, 'dy': dy, 'neighbor_frac': 0.5, 'steps_remaining': n}
        self._propagation = None
        # record last tentative move (idx, dx, dy) produced by perturb
        self._last_move = None

    def _movement_radius(self, path):
        segments = path.get_segments()
        if len(segments) == 0:
            return 5.0
        avg_seg = np.mean(segments[:, 3])
        return max(1.0, 0.25 * avg_seg)

    def _make_candidate(self, path_cls, dem, pts, idx, dx, dy):
        """Build a candidate xyzPath from raw points `pts` (numpy or list).

        To avoid repeated `get_points()` calls and many `add_point` calls we
        construct the points list directly and assign to `new_path.points`.
        """
        new_points = []
        # pts may be numpy array or list-of-lists
        for i in range(len(pts)):
            pt = pts[i]
            if i == idx:
                new_points.append([float(pt[0]) + dx, float(pt[1]) + dy, float(pt[2])])
            else:
                new_points.append([float(pt[0]), float(pt[1]), float(pt[2])])

        new_path = path_cls(dem)
        new_path.points = new_points
        if new_path and new_path.dem:
            new_path.update_z_values()
        return new_path

    def perturb(self, path, cost_function=None, stop_event=None):
        if path.get_point_count() < 3:
            return path

        pts = path.get_points()
        n = len(pts)

        # pick a random interior point
        idx = random.randint(1, n - 2)

        radius = self._movement_radius(path)

        # baseline
        baseline_cost = cost_function(path) if cost_function else float('inf')
        best_path = path
        best_cost = baseline_cost

        # If there is an active propagation plan, prioritize producing a propagated candidate
        if self._propagation is not None and self._propagation.get('steps_remaining', 0) > 0:
            center = self._propagation['center']
            dx = self._propagation['dx']
            dy = self._propagation['dy']
            frac = self._propagation.get('neighbor_frac', 0.5)

            pts = path.get_points()
            # build points list directly for candidate
            new_points = []
            for i in range(len(pts)):
                pt = pts[i]
                if i == center:
                    new_points.append([float(pt[0]) + dx, float(pt[1]) + dy, float(pt[2])])
                elif i == center - 1 or i == center + 1:
                    new_points.append([float(pt[0]) + dx * frac, float(pt[1]) + dy * frac, float(pt[2])])
                else:
                    new_points.append([float(pt[0]), float(pt[1]), float(pt[2])])

            new_path = path.__class__(path.dem)
            new_path.points = new_points
            if new_path and new_path.dem:
                new_path.update_z_values()

            # record last move for solver notification
            self._last_move = (center, dx, dy)

            # do not perform sampling this call; return candidate for solver to evaluate
            return new_path

        # coarse sampling around chosen vertex
        # local references to avoid attribute lookups in loop
        path_cls = path.__class__
        dem = path.dem
        pts = path.get_points()
        for s in range(self.samples):
            # quick stop check to reduce latency
            if stop_event is not None:
                try:
                    if stop_event.is_set():
                        return best_path
                except Exception:
                    pass
            angle = random.uniform(0, 2 * math.pi)
            r = random.uniform(0, radius)
            dx = r * math.cos(angle)
            dy = r * math.sin(angle)
            cand = self._make_candidate(path_cls, dem, pts, idx, dx, dy)
            if cost_function:
                # check stop_event before expensive cost evaluation
                if stop_event is not None:
                    try:
                        if stop_event.is_set():
                            return best_path
                    except Exception:
                        pass
                try:
                    c = cost_function(cand)
                except Exception:
                    c = float('inf')
            else:
                c = 0.0
            if c < best_cost:
                best_cost = c
                best_path = cand
                # record candidate move: compute displacement of idx
                moved_pt = cand.get_point(idx)
                orig_pt = pts[idx]
                self._last_move = (idx, moved_pt[0] - orig_pt[0], moved_pt[1] - orig_pt[1])
                try:
                    print(f"SinglePointMover: improvement found at idx={idx}, dcost={best_cost - baseline_cost:.3f}")
                except Exception:
                    pass

        # local hill-climb around best candidate (if improved)
        climb_steps = 0
        while climb_steps < self.max_climb_steps:
            improved = False
            # sample a smaller neighborhood
            for _ in range(max(8, self.samples // 2)):
                # stop check inside inner hill-climb loop
                if stop_event is not None:
                    try:
                        if stop_event.is_set():
                            return best_path
                    except Exception:
                        pass
                angle = random.uniform(0, 2 * math.pi)
                r = random.uniform(0, radius * (0.5 ** (climb_steps + 1)))
                dx = r * math.cos(angle)
                dy = r * math.sin(angle)
                # use pts from best_path if available to build candidate faster
                cand_pts = best_path.get_points()
                cand = self._make_candidate(path_cls, dem, cand_pts, idx, dx, dy)
                if cost_function:
                    # check stop_event before expensive cost evaluation
                    if stop_event is not None:
                        try:
                            if stop_event.is_set():
                                return best_path
                        except Exception:
                            pass
                    try:
                        c = cost_function(cand)
                    except Exception:
                        c = float('inf')
                else:
                    c = 0.0
                if c < best_cost:
                    best_cost = c
                    best_path = cand
                    improved = True
                    # record last move for solver notification
                    moved_pt = cand.get_point(idx)
                    orig_pt = pts[idx]
                    self._last_move = (idx, moved_pt[0] - orig_pt[0], moved_pt[1] - orig_pt[1])
                    try:
                        print(f"SinglePointMover: hill-climb improved idx={idx}, dcost={best_cost - baseline_cost:.3f}")
                    except Exception:
                        pass
            if not improved:
                break
            climb_steps += 1

        # reset _last_move if no improvement found
        if best_path is path:
            self._last_move = None
        return best_path

    def on_move_accepted(self, old_path, new_path):
        """
        Called by the optimizer when a move produced by this perturber was accepted.
        Use the recorded `_last_move` to seed a propagation plan that nudges
        neighboring nodes in subsequent iterations.
        """
        if not self._last_move:
            return
        idx, dx, dy = self._last_move
        # If a propagation is already running, decrement its counter (we just accepted one step)
        if self._propagation is not None and self._propagation.get('center') == idx:
            # adopt the latest dx/dy (in case center moved further) and decrement
            self._propagation['dx'] = dx
            self._propagation['dy'] = dy
            self._propagation['steps_remaining'] = max(0, self._propagation.get('steps_remaining', 1) - 1)
            if self._propagation['steps_remaining'] == 0:
                self._propagation = None
            return

        # start a new propagation plan: apply on next iterations until limit
        self._propagation = {
            'center': idx,
            'dx': dx,
            'dy': dy,
            'neighbor_frac': 0.5,
            'steps_remaining': 3,
        }


# Example usage:
# mover = SinglePointMover(spacing=10.0)
# new_path = mover.perturb(path, cost_function)
