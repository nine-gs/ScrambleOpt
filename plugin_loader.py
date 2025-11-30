import os
import sys
import importlib.util

class PluginLoader:
    """Load solvers and cost functions dynamically from files"""
    
    @staticmethod
    def load_solvers():
        """
        Load all solvers from the solvers folder.
        Returns dict of {solver_name: module}
        """
        solvers = {}
        solvers_dir = os.path.join(os.path.dirname(__file__), 'solvers')
        
        if not os.path.exists(solvers_dir):
            return solvers
        
        for filename in os.listdir(solvers_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(
                        f"solvers.{module_name}",
                        os.path.join(solvers_dir, filename)
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Get the solver name from the module
                    if hasattr(module, 'name'):
                        solvers[module.name] = module
                except Exception as e:
                    print(f"Error loading solver {filename}: {e}")
        
        return solvers
    
    @staticmethod
    def load_cost_functions():
        """
        Load all cost functions from cost_functions.py.
        Returns dict of {function_display_name: function}
        Uses the docstring of each function as its display name.
        """
        cost_funcs = {}
        
        try:
            import cost_functions as cf_module
            import inspect
            
            # Get all functions defined in the module
            for name, obj in inspect.getmembers(cf_module, inspect.isfunction):
                # Only include functions defined in this module, not imported ones
                if obj.__module__ == 'cost_functions':
                    # Use the function's docstring as the display name
                    display_name = obj.__doc__ if obj.__doc__ else name
                    display_name = display_name.strip()
                    cost_funcs[display_name] = obj
        except Exception as e:
            print(f"Error loading cost functions: {e}")
        
        return cost_funcs
