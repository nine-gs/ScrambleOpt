from path import xyzPath
from cost_functions import acsm_equation
from solvers.simulatedAnneal import optimize
import perturbers.singlePointMover as spm

# Dummy DEM and path for testing

class DummyDEM:
    def get_elevation(self, x, y):
        # Return a flat elevation for testing
        return 0.0

def make_test_path():
    dem = DummyDEM()
    path = xyzPath(dem)
    # Add points (x, y) spaced 10m apart
    for i in range(10):
        path.add_point(i*10, 0)
    return path


if __name__ == "__main__":
    path = make_test_path()
    time = 1.0  # Dummy time value
    def cost_fn(p):
        return acsm_equation(p, time)
    print("Initial cost:", cost_fn(path))
    best_path, best_cost = optimize(path, cost_fn, [spm], single_point_spacing=10.0)
    print("Optimized cost:", best_cost)
    print("Optimized points:", best_path.get_points())
