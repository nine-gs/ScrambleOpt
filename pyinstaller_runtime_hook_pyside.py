# Runtime hook to ensure bundled PySide6 DLLs and plugins are loaded
import sys
import os

def _prepend_path(pth):
    if not pth:
        return
    cur = os.environ.get('PATH', '')
    if pth not in cur:
        os.environ['PATH'] = pth + os.pathsep + cur

# If frozen, PyInstaller extracts packages to sys._MEIPASS
meipass = getattr(sys, '_MEIPASS', None)
if meipass:
    pyside_dir = os.path.join(meipass, 'PySide6')
    # Prepend the extracted PySide6 binary dir to PATH so system Qt DLLs don't override
    if os.path.isdir(pyside_dir):
        _prepend_path(pyside_dir)

    # If plugins exist (e.g., platforms), set QT_PLUGIN_PATH so Qt finds bundled plugins
    plugins_dir = os.path.join(pyside_dir, 'plugins')
    if os.path.isdir(plugins_dir):
        qt_plugin_path = os.environ.get('QT_PLUGIN_PATH', '')
        if plugins_dir not in qt_plugin_path:
            os.environ['QT_PLUGIN_PATH'] = plugins_dir + (os.pathsep + qt_plugin_path if qt_plugin_path else '')
else:
    # Development run: ensure venv PySide6 folder is on PATH to avoid mixing system Qt
    try:
        import PySide6
        venv_pyside = os.path.dirname(PySide6.__file__)
        _prepend_path(venv_pyside)
    except Exception:
        pass
